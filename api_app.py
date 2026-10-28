"""Direct HTTP client for the public BUAA self-service web protocol."""
import base64
import json
import os
import queue
import re
import threading
import time
from http.cookiejar import Cookie
from pathlib import Path
from urllib.parse import urljoin, urlsplit
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

import requests
from bs4 import BeautifulSoup
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding

BASE = 'https://zfw.buaa.edu.cn'


class SessionExpired(ValueError):
    pass


class Store:
    def __init__(self, directory=None):
        self.directory = Path(directory) if directory else Path(os.environ.get('LOCALAPPDATA', '.')) / 'BuaaTraffic'

    def load(self, name, default, encrypted=False):
        path = self.directory / name
        if not path.exists():
            return default
        raw = path.read_bytes()
        if encrypted:
            import win32crypt
            raw = win32crypt.CryptUnprotectData(raw, None, None, None, 0)[1]
        return json.loads(raw)

    def save(self, name, data, encrypted=False):
        raw = json.dumps(data, ensure_ascii=False).encode('utf-8')
        if encrypted:
            import win32crypt
            # CryptProtectData returns bytes; only UnprotectData returns a tuple.
            raw = win32crypt.CryptProtectData(raw, 'BUAA desktop', None, None, None, 0)
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / name
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_bytes(raw)
        temp.replace(path)


def cookie_records(jar):
    records = []
    for cookie in jar:
        record = vars(cookie).copy()
        record['rest'] = record.pop('_rest')
        records.append(record)
    return records


def restore_cookies(jar, data):
    if isinstance(data, dict):  # Compatibility with the first interface version.
        jar.update(requests.utils.cookiejar_from_dict(data))
    else:
        for record in data:
            jar.set_cookie(Cookie(**record))


def parse_home(html):
    soup = BeautifulSoup(html, 'html.parser')
    for table in soup.select('table'):
        rows = [[c.get_text(' ', strip=True) for c in row.select('th,td')] for row in table.select('tr')]
        for i, row in enumerate(rows):
            heads = [re.sub(r'\s+', '', s) for s in row]
            if '已用流量' in heads and any('计费流量剩余' in s for s in heads):
                records = [dict(zip(heads, vals)) for vals in rows[i+1:] if len(vals) == len(heads)]
                if records:
                    return records
    if soup.select_one('#loginform-password'):
        raise SessionExpired('登录已失效，请获取验证码并重新登录。')
    raise ValueError('未找到产品流量表；网站可能变更了页面。')


def value(record, label):
    return next((v for k, v in record.items() if label in k), '—')


def captcha_image_data(raw):
    """Accept only small PNG/GIF CAPTCHA images supported by native Tk."""
    if len(raw) > 512 * 1024:
        raise ValueError('验证码图片异常大，请重新获取。')
    if raw.startswith(b'\x89PNG\r\n\x1a\n') and len(raw) >= 24:
        width, height = int.from_bytes(raw[16:20], 'big'), int.from_bytes(raw[20:24], 'big')
    elif raw[:6] in (b'GIF87a', b'GIF89a') and len(raw) >= 10:
        width, height = int.from_bytes(raw[6:8], 'little'), int.from_bytes(raw[8:10], 'little')
    else:
        raise ValueError('服务器未返回 PNG/GIF 验证码图片，请确认校园网站可正常访问。')
    if not (0 < width <= 1200 and 0 < height <= 400):
        raise ValueError('验证码图片尺寸异常，请重新获取。')
    return base64.b64encode(raw)


class Client:
    def __init__(self, store=None):
        self.store = store or Store()
        self.storage_notice = ''
        self.session = requests.Session()
        # Campus service is reached directly; do not inherit a development-shell proxy.
        self.session.trust_env = False
        self.session.headers.update({'User-Agent': 'BuaaTrafficDesktop/2.1.1', 'Referer': BASE + '/'})
        self.soup = None
        self.pending = None
        try:
            restore_cookies(self.session.cookies, self.store.load('session.dpapi', [], encrypted=True))
        except Exception as exc:
            self.storage_notice = '读取本机会话失败：' + str(exc)

    def save_session(self):
        try:
            self.store.save('session.dpapi', cookie_records(self.session.cookies), encrypted=True)
        except Exception as exc:
            self.storage_notice = '会话保存失败，下次启动可能需要重新登录：' + str(exc)

    def request(self, method, path, **kwargs):
        if not path.startswith('/') or path.startswith('//'):
            raise ValueError('拒绝非本站请求')
        url = BASE + path
        for _ in range(6):
            target = urlsplit(url)
            if (target.scheme != 'https' or target.hostname != 'zfw.buaa.edu.cn'
                    or target.port not in (None, 443) or target.username or target.password):
                raise ValueError('网站跳转到非本站 HTTPS 地址，已停止请求以保护登录信息。')
            response = self.session.request(method, url, timeout=(8, 20), allow_redirects=False, **kwargs)
            if not response.is_redirect:
                response.raise_for_status()
                response.encoding = 'utf-8'
                return response
            location = response.headers['Location']
            status = response.status_code
            response.close()
            url = urljoin(url, location)
            if status == 303 or (status in (301, 302) and method.upper() == 'POST'):
                method = 'GET'
                kwargs.pop('data', None)
                kwargs.pop('json', None)
        raise ValueError('网站跳转次数过多，请稍后重试。')

    def csrf(self):
        token = self.soup.select_one('meta[name="csrf-token"]')
        param = self.soup.select_one('meta[name="csrf-param"]')
        if not token or not param:
            raise ValueError('网页缺少 CSRF 信息，请重新获取验证码。')
        return {param['content']: token['content']}

    def captcha(self):
        self.pending = None
        self.soup = BeautifulSoup(self.request('GET', '/').text, 'html.parser')
        image = self.soup.select_one('#loginform-verifycode-image')
        if image is None:
            return None
        return self.request('GET', image['src']).content

    @staticmethod
    def json_response(response):
        result = response.json()
        return json.loads(result) if isinstance(result, str) else result

    def login(self, username, password, code):
        if not username or not password or not code:
            raise ValueError('请填写学号、密码和图形验证码。')
        if self.soup is None:
            raise ValueError('请先获取验证码。')
        public = self.soup.select_one('#public')
        if public is None:
            raise ValueError('找不到登录公钥，请重新获取验证码。')
        key = serialization.load_pem_public_key(public['value'].encode())
        encrypted = base64.b64encode(key.encrypt(password.encode('utf-8'), padding.PKCS1v15())).decode()
        form = {**self.csrf(), 'LoginForm[username]': username,
                'LoginForm[password]': encrypted, 'LoginForm[verifyCode]': code,
                'LoginForm[smsCode]': ''}
        result = self.json_response(self.request('POST', '/site/validate-user', data=form,
                                   headers={'X-Requested-With': 'XMLHttpRequest'}))
        if not result.get('success'):
            raise ValueError(str(result.get('message', '账号验证失败，请重新获取验证码。')))
        if result.get('inputSms'):
            self.pending = form
            return ('sms', str(result.get('message', '请输入学校发送的短信验证码。')))
        return ('data', self.finish(form))

    def sms(self, code):
        if not self.pending:
            raise ValueError('短信登录已过期，请重新登录。')
        form = self.pending.copy()
        result = self.json_response(self.request('POST', '/site/validate-smscode', data={
            **self.csrf(), 'uname': form['LoginForm[username]'], 'code': code},
            headers={'X-Requested-With': 'XMLHttpRequest'}))
        if not result.get('success'):
            raise ValueError(str(result.get('message', '短信验证码错误。')))
        form['LoginForm[smsCode]'] = code
        self.pending = None
        return self.finish(form)

    def finish(self, form):
        self.request('POST', '/', data=form)
        return self.home()

    def home(self):
        html = self.request('GET', '/home').text
        self.soup = BeautifulSoup(html, 'html.parser')
        result = parse_home(html)
        self.save_session()  # Keep rotated cookies, including their domain/path/expiry.
        return result

    def offline(self):
        self.home()  # Fresh CSRF token and authenticated state; never retry the POST.
        link = self.soup.select_one('a[href="/home/onekey"][data-method="post"]')
        if link is None:
            raise ValueError('当前页面未提供预期的下线入口，已停止操作。')
        try:
            self.request('POST', '/home/onekey', data=self.csrf())
        except requests.RequestException as exc:
            raise ValueError('下线请求结果未知，可能已断网；不会重复提交。请重新联网后刷新余量。') from exc
        # Read-only retries allow the server time to settle; never claim settlement is complete.
        last = None
        for _ in range(3):
            time.sleep(2)
            try:
                last = self.home()
            except requests.RequestException:
                continue
        if last is None:
            raise ValueError('已发送下线请求，后续查询失败。请重新联网后刷新余量。')
        return last


class App:
    def __init__(self, root, store=None, start_worker=True):
        self.root = root
        self.store = store or Store()
        root.title('北航流量助手 · 接口版 2.1.1')
        root.geometry('620x760')
        root.minsize(620, 760)
        self.jobs, self.results = queue.Queue(), queue.Queue()
        self.busy = False
        self.authenticated = False
        self.next_refresh = self.next_offline = None
        self.active_command = None
        self.active_auto = False
        self.closing = False
        load_notice = ''
        try:
            settings = self.store.load('settings.json', {})
            credentials = self.store.load('credentials.dpapi', {}, encrypted=True)
        except Exception as exc:
            settings, credentials = {}, {}
            load_notice = '本机设置读取失败：' + str(exc)
        self.auto = tk.BooleanVar(value=settings.get('auto_refresh', False))
        self.auto_offline = tk.BooleanVar(value=settings.get('auto_offline', False))
        self.refresh_minutes = tk.StringVar(value=str(settings.get('refresh_minutes', 5)))
        self.offline_minutes = tk.StringVar(value=str(settings.get('offline_minutes', 60)))
        self.remember_user = tk.BooleanVar(value=settings.get('remember_user', False))
        self.remember_password = tk.BooleanVar(value=settings.get('remember_password', False))
        self.countdown = tk.StringVar(value='正在恢复上次会话…')
        self.remaining = tk.StringVar(value='— GB')
        self.detail = tk.StringVar(value='尚未查询')
        self.status = tk.StringVar(value=load_notice or '启动时自动尝试复用上次 Cookie；有效时无需重新登录。')
        self.user, self.password, self.code = (tk.StringVar() for _ in range(3))
        if self.remember_user.get():
            self.user.set(credentials.get('username', ''))
        if self.remember_password.get():
            self.password.set(credentials.get('password', ''))
        frame = tk.Frame(root, padx=24, pady=20)
        frame.pack(fill='both', expand=True)
        tk.Label(frame, text='校园网余量', font=('Microsoft YaHei UI', 21, 'bold')).pack(anchor='w')
        tk.Label(frame, text='计费流量剩余 · 网站记录值', fg='#566578').pack(anchor='w', pady=(6, 0))
        tk.Label(frame, textvariable=self.remaining, font=('Microsoft YaHei UI', 34, 'bold'), fg='#167866').pack(anchor='w')
        tk.Label(frame, textvariable=self.detail, justify='left').pack(anchor='w')
        row = tk.Frame(frame)
        row.pack(fill='x', pady=14)
        self.buttons = []
        self.button(row, '刷新余量', lambda: self.submit('home'))
        self.button(row, '下线并自动重查…', self.offline)
        timers = tk.LabelFrame(frame, text='定时任务 · 程序运行且已登录时生效', padx=10, pady=8)
        timers.pack(fill='x', pady=4)
        for i, (text, enabled, interval, choices) in enumerate([
            ('自动刷新余量，每', self.auto, self.refresh_minutes, (1, 2, 5, 10, 15, 30, 60)),
            ('自动下线并重查，每', self.auto_offline, self.offline_minutes, (1, 5, 10, 15, 30, 60, 120, 180, 360))]):
            tk.Checkbutton(timers, text=text, variable=enabled, command=lambda e=enabled: self.timer_changed(e)).grid(row=i, column=0, sticky='w')
            box = ttk.Combobox(timers, textvariable=interval, values=choices, state='readonly', width=6)
            box.grid(row=i, column=1, padx=6, pady=4)
            box.bind('<<ComboboxSelected>>', lambda _: self.timer_changed())
            tk.Label(timers, text='分钟').grid(row=i, column=2)
        tk.Label(timers, textvariable=self.countdown, fg='#566578').grid(row=2, column=0, columnspan=3, sticky='w', pady=4)
        login = tk.LabelFrame(frame, text='登录 · 验证码在此填写', padx=12, pady=10)
        login.pack(fill='x', pady=12)
        for i, (label, var, secret) in enumerate([('学号', self.user, False), ('密码', self.password, True), ('验证码', self.code, False)]):
            tk.Label(login, text=label).grid(row=i, column=0, sticky='w', pady=4)
            tk.Entry(login, textvariable=var, show='•' if secret else '', width=24).grid(row=i, column=1, padx=8)
        self.captcha_label = tk.Label(login, text='点击获取验证码', width=19)
        self.captcha_label.grid(row=0, column=2, rowspan=2)
        buttons = tk.Frame(login)
        buttons.grid(row=3, column=0, columnspan=3, sticky='w', pady=(8, 0))
        self.button(buttons, '获取 / 更换验证码', lambda: self.submit('captcha'))
        self.button(buttons, '登录', self.login)
        remember = tk.Frame(login)
        remember.grid(row=4, column=0, columnspan=3, sticky='w', pady=(8, 0))
        tk.Checkbutton(remember, text='记住账号', variable=self.remember_user, command=lambda: self.credentials_changed('user')).pack(side='left')
        tk.Checkbutton(remember, text='保存密码（Windows 加密）', variable=self.remember_password, command=lambda: self.credentials_changed('password')).pack(side='left')
        tk.Label(frame, text='在线用量可能尚未结算。下线会断开账号下的在线设备。\n下线后自动查询约 6 秒；最终仍以服务器结算为准。', justify='left', fg='#806227').pack(anchor='w', pady=6)
        tk.Label(frame, textvariable=self.status, wraplength=520, justify='left', fg='#42556c').pack(anchor='w', pady=8)
        if start_worker:
            threading.Thread(target=self.worker, daemon=True).start()
            root.after(300, lambda: self.submit('home'))
        root.after(150, self.poll)
        root.after(1000, self.tick)
        root.protocol('WM_DELETE_WINDOW', self.close)

    def persist(self):
        try:
            self.store.save('settings.json', {
                'auto_refresh': self.auto.get(), 'auto_offline': self.auto_offline.get(),
                'refresh_minutes': int(self.refresh_minutes.get()), 'offline_minutes': int(self.offline_minutes.get()),
                'remember_user': self.remember_user.get(), 'remember_password': self.remember_password.get()})
            self.store.save('credentials.dpapi', {
                'username': self.user.get().strip() if self.remember_user.get() else '',
                'password': self.password.get() if self.remember_password.get() else ''}, encrypted=True)
            return True
        except Exception as exc:
            self.status.set('本机设置保存失败：' + str(exc))
            return False

    def credentials_changed(self, source):
        if source == 'password' and self.remember_password.get():
            self.remember_user.set(True)
        if source == 'user' and not self.remember_user.get():
            self.remember_password.set(False)
        self.persist()

    def reset_timers(self):
        now = time.monotonic()
        self.next_refresh = now + int(self.refresh_minutes.get()) * 60
        self.next_offline = now + int(self.offline_minutes.get()) * 60

    def timer_changed(self, enabled=None):
        if enabled is self.auto_offline and self.auto_offline.get():
            if not messagebox.askokcancel('开启自动下线', '启用后，每隔选定分钟数会自动执行一键下线，断开账号下的在线设备，并重查余量。\n定时执行时不再逐次弹窗；本工具不会自动重连校园网。\n\n确认开启？', parent=self.root):
                self.auto_offline.set(False)
        self.reset_timers()
        self.persist()

    def close(self):
        self.persist()
        self.closing = True
        self.root.destroy()

    def button(self, parent, text, command):
        button = tk.Button(parent, text=text, command=command, padx=10, pady=5)
        button.pack(side='left', padx=(0, 8))
        self.buttons.append(button)

    def submit(self, command, *args, automatic=False):
        if self.busy:
            return
        self.busy = True
        self.active_command = command
        self.active_auto = automatic
        for button in self.buttons:
            button.config(state='disabled')
        self.status.set('请求中…' if command != 'offline' else '正在下线并等待结算，随后自动重查…')
        self.jobs.put((command, args))

    def login(self):
        args = (self.user.get().strip(), self.password.get(), self.code.get().strip())
        if not self.persist():
            return
        if not self.remember_password.get():
            self.password.set('')
        self.submit('login', *args)

    def offline(self):
        if messagebox.askokcancel('确认断网影响', '将通过接口执行一键下线，断开账号下的在线设备，然后自动查询余量。\n若本机断网，需要重新连接校园网。现在执行？', parent=self.root):
            self.submit('offline')

    def worker(self):
        client = Client(self.store)
        while True:
            command, args = self.jobs.get()
            try:
                result = getattr(client, command)(*args)
                if command == 'login':
                    self.results.put(result)
                else:
                    self.results.put(('captcha' if command == 'captcha' else 'offline_data' if command == 'offline' else 'data', result))
            except SessionExpired as exc:
                self.results.put(('expired', str(exc)))
            except Exception as exc:
                self.results.put(('error', str(exc)))
            finally:
                if client.storage_notice:
                    self.results.put(('notice', client.storage_notice))
                    client.storage_notice = ''
                self.results.put(('idle', None))

    def poll(self):
        sms_prompt = None
        try:
            while True:
                kind, result = self.results.get_nowait()
                if kind == 'idle':
                    self.busy = False
                    now = time.monotonic()
                    if self.active_command in ('home', 'offline', 'login', 'sms'):
                        self.next_refresh = now + int(self.refresh_minutes.get()) * 60
                    if self.active_command == 'offline':
                        self.next_offline = now + int(self.offline_minutes.get()) * 60
                    for button in self.buttons:
                        button.config(state='normal')
                elif kind in ('data', 'offline_data'):
                    if not self.authenticated:
                        self.reset_timers()
                    self.authenticated = True
                    record = result[0]
                    self.remaining.set(value(record, '计费流量剩余'))
                    self.detail.set('已用：' + value(record, '已用流量') + '    免费剩余：' + value(record, '免费流量剩余') + '\n结算日期：' + value(record, '结算日期'))
                    self.status.set(('下线请求已发送，已重查；结算完成时间以学校服务器为准。' if kind == 'offline_data' else '查询成功。') + ' 更新于 ' + time.strftime('%H:%M:%S') + (f'，显示 {len(result)} 个产品中的第一个。' if len(result) > 1 else ''))
                elif kind == 'captcha':
                    if result is None:
                        self.status.set('当前会话已登录，点击刷新余量即可。')
                    else:
                        try:
                            photo = tk.PhotoImage(data=captcha_image_data(result))
                            scale = max(1, (photo.width() + 149) // 150, (photo.height() + 63) // 64)
                            self.photo = photo.subsample(scale, scale)
                        except (ValueError, tk.TclError) as exc:
                            self.status.set('验证码图片读取失败：' + str(exc))
                            continue
                        self.captcha_label.config(image=self.photo, text='', width=150)
                        self.code.set('')
                        self.status.set('验证码已获取，请填写后登录。')
                elif kind == 'sms':
                    sms_prompt = result
                elif kind in ('error', 'expired'):
                    if kind == 'expired':
                        self.authenticated = False
                    if self.active_command == 'offline':
                        self.auto_offline.set(False)
                        self.persist()
                    self.status.set('操作失败；已有数字可能过时。' + result)
                    if self.active_command == 'offline':
                        self.status.set(self.status.get() + ' 自动下线已关闭，请检查网络后重新启用。')
                elif kind == 'notice':
                    self.status.set(self.status.get() + '\n' + result)
        except queue.Empty:
            pass
        if sms_prompt:
            code = simpledialog.askstring('短信验证', sms_prompt, parent=self.root)
            if code:
                self.submit('sms', code.strip())
        self.root.after(150, self.poll)

    def tick(self):
        now = time.monotonic()
        if not self.authenticated:
            self.countdown.set('未登录 / 会话失效，定时任务等待登录成功')
        else:
            if self.next_refresh is None:
                self.reset_timers()
            labels = []
            if self.auto.get():
                labels.append(f'下次刷新 {max(0, int(self.next_refresh - now))} 秒')
            if self.auto_offline.get():
                labels.append(f'下次下线 {max(0, int(self.next_offline - now))} 秒')
            self.countdown.set('  ·  '.join(labels) or '定时任务已关闭')
            if not self.busy:
                if self.auto_offline.get() and now >= self.next_offline:
                    self.submit('offline', automatic=True)
                elif self.auto.get() and now >= self.next_refresh:
                    self.submit('home', automatic=True)
        self.root.after(1000, self.tick)


if __name__ == '__main__':
    root = tk.Tk()
    App(root)
    root.mainloop()
