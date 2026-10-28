"""Direct HTTP client for the public BUAA self-service web protocol."""
import base64
import io
import json
import os
import queue
import re
import threading
import time
from http.cookiejar import Cookie
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

import requests
from bs4 import BeautifulSoup
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from PIL import Image, ImageTk

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


class Client:
    def __init__(self, store=None):
        self.store = store or Store()
        self.storage_notice = ''
        self.session = requests.Session()
        # Campus service is reached directly; do not inherit a development-shell proxy.
        self.session.trust_env = False
        self.session.headers.update({'User-Agent': 'BuaaTrafficDesktop/2.2', 'Referer': BASE + '/'})
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
        response = self.session.request(method, BASE + path, timeout=(8, 20), **kwargs)
        response.raise_for_status()
        response.encoding = 'utf-8'
        return response

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
        root.title('校园网助手 · 北航 · 2.2')
        root.geometry('1040x850')
        root.minsize(900, 620)
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
        from desktop_ui import DesktopView
        self.buttons = []
        self.view = DesktopView(self)
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

    def submit(self, command, *args, automatic=False):
        if self.busy:
            return
        self.busy = True
        self.active_command = command
        self.active_auto = automatic
        self.view.set_busy(True)
        if command in ('login', 'sms'):
            self.view.login_hint.set('正在验证登录信息…')
        for button in self.buttons:
            button.config(state='disabled')
        self.status.set('请求中…' if command != 'offline' else '正在下线并等待结算，随后自动重查…')
        self.jobs.put((command, args))

    def login(self):
        if self.busy:
            return
        for name, var in [('学号', self.user), ('密码', self.password), ('验证码', self.code)]:
            if not var.get().strip():
                self.view.login_hint.set('请填写' + name + '。')
                self.view.entries[name].focus_set()
                return
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
                    self.view.set_busy(False)
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
                    self.view.show_record(record, time.strftime('%H:%M:%S'))
                    self.view.login_hint.set('会话已恢复，可直接查询。')
                    self.remaining.set(value(record, '计费流量剩余'))
                    self.detail.set('已用：' + value(record, '已用流量') + '    免费剩余：' + value(record, '免费流量剩余') + '\n结算日期：' + value(record, '结算日期'))
                    self.status.set(('下线请求已发送，已重查；结算完成时间以学校服务器为准。' if kind == 'offline_data' else '查询成功。') + ' 更新于 ' + time.strftime('%H:%M:%S') + (f'，显示 {len(result)} 个产品中的第一个。' if len(result) > 1 else ''))
                elif kind == 'captcha':
                    if result is None:
                        self.status.set('当前会话已登录，点击刷新余量即可。')
                    else:
                        image = Image.open(io.BytesIO(result))
                        image.thumbnail((150, 64))
                        self.photo = ImageTk.PhotoImage(image)
                        self.captcha_label.config(image=self.photo, text='', width=150, height=50)
                        self.code.set('')
                        self.view.login_hint.set('验证码已更新，填写后按 Enter 登录。')
                        self.status.set('验证码已获取，请填写后登录。')
                elif kind == 'sms':
                    sms_prompt = result
                elif kind in ('error', 'expired'):
                    self.view.connection.set('需要登录' if kind == 'expired' else '操作未完成')
                    if self.active_command in ('login', 'sms', 'captcha') or kind == 'expired':
                        self.view.login_hint.set(result)
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
