"""Restrained, single-column desktop presentation; no network or storage logic."""
import tkinter as tk
import time
from tkinter import ttk

COLORS = {
    'background': '#F7F8F7', 'field': '#FFFFFF', 'text': '#243431',
    'muted': '#56645F', 'line': '#D7DFDB', 'border': '#89958F',
    'accent': '#11685C', 'hover': '#0D554B', 'secondary': '#E7ECE9',
    'danger': '#9E392F', 'disabled': '#63716A',
}
FONT = 'Microsoft YaHei UI'


class CompactView:
    def __init__(self, app):
        self.app, self.root = app, app.root
        self.last_update = None
        self.connection = tk.StringVar(value='等待登录')
        self.updated = tk.StringVar(value='')
        self.login_hint = tk.StringVar(value='先获取验证码，再填写登录信息。')
        self.root.configure(bg=COLORS['background'])
        self.root.option_add('*Font', (FONT, 10))
        style = ttk.Style(self.root)
        style.theme_use('clam')
        style.configure('Compact.TButton', font=(FONT, 10), padding=(12, 7),
                        background=COLORS['secondary'], foreground=COLORS['text'],
                        borderwidth=0, focusthickness=2, focuscolor=COLORS['accent'])
        style.map('Compact.TButton', background=[('disabled', '#EDF0EE'), ('pressed', '#D1DCD5'), ('active', '#DCE5DF')],
                  foreground=[('disabled', COLORS['disabled'])])
        style.configure('Primary.Compact.TButton', font=(FONT, 10, 'bold'),
                        background=COLORS['accent'], foreground='white', focuscolor='white')
        style.map('Primary.Compact.TButton', background=[('disabled', '#DDE5DF'), ('pressed', '#09453D'), ('active', COLORS['hover'])],
                  foreground=[('disabled', COLORS['disabled'])])
        style.configure('Danger.Compact.TButton', background=COLORS['background'], foreground=COLORS['danger'])
        style.map('Danger.Compact.TButton', background=[('disabled', COLORS['background']), ('active', '#F4E6E2')],
                  foreground=[('disabled', COLORS['disabled'])])
        style.configure('Compact.TEntry', font=(FONT, 10), padding=(8, 5), foreground=COLORS['text'],
                        fieldbackground=COLORS['field'], bordercolor=COLORS['border'],
                        lightcolor=COLORS['border'], darkcolor=COLORS['border'])
        style.map('Compact.TEntry', bordercolor=[('focus', COLORS['accent'])],
                  lightcolor=[('focus', COLORS['accent'])], darkcolor=[('focus', COLORS['accent'])])
        style.configure('Compact.TCombobox', padding=(6, 3), foreground=COLORS['text'], bordercolor=COLORS['border'], arrowsize=13)
        style.map('Compact.TCombobox', fieldbackground=[('readonly', 'white')],
                  foreground=[('readonly', COLORS['text'])], selectbackground=[('readonly', 'white')],
                  selectforeground=[('readonly', COLORS['text'])])
        style.configure('Compact.TCheckbutton', font=(FONT, 10), background=COLORS['background'], foreground=COLORS['text'], padding=(0, 3))
        style.map('Compact.TCheckbutton', background=[('active', COLORS['background'])])
        style.configure('Compact.Horizontal.TProgressbar', background=COLORS['accent'], borderwidth=0)

        shell = tk.Frame(self.root, bg=COLORS['background'])
        shell.pack(fill='both', expand=True)
        self.canvas = tk.Canvas(shell, bg=COLORS['background'], highlightthickness=0)
        self.scroll = ttk.Scrollbar(shell, orient='vertical', command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scroll.set)
        self.canvas.pack(side='left', fill='both', expand=True)
        self.body = tk.Frame(self.canvas, bg=COLORS['background'], padx=24, pady=14)
        self.body_window = self.canvas.create_window(0, 0, window=self.body, anchor='nw')
        self.canvas.bind('<Configure>', self.resize)
        self.body.bind('<Configure>', self.resize)
        self.root.bind('<MouseWheel>', self.wheel, add='+')
        self.root.bind('<FocusIn>', self.focus_visible, add='+')

        heading = self.row(self.body)
        self.label(heading, '校园网余量', size=18, bold=True).pack(side='left')
        self.connection_label = self.label(heading, variable=self.connection, size=9)
        self.connection_label.pack(side='right')
        metric = self.row(self.body)
        metric.pack_configure(pady=(8, 0))
        self.label(metric, variable=app.remaining, size=30, bold=True, color=COLORS['accent']).pack(side='left')
        self.label(metric, '计费流量剩余\n网站记录值', size=9).pack(side='left', padx=(16, 0))
        details = self.row(self.body)
        self.label(details, variable=app.detail, size=10).pack(side='left', anchor='n')
        self.label(details, variable=self.updated, size=9).pack(side='right', anchor='n')
        actions = self.row(self.body)
        actions.pack_configure(pady=(10, 0))
        self.refresh = self.button(actions, '刷新余量', lambda: app.submit('home'), 'Primary.Compact.TButton', width=12)
        self.refresh.pack(side='left', padx=(0, 8))
        self.button(actions, '下线并自动重查…', app.offline, 'Danger.Compact.TButton').pack(side='left')

        self.section('定时任务')
        timers = self.row(self.body)
        for i, (text, enabled, minutes, choices) in enumerate([
            ('自动刷新余量，每', app.auto, app.refresh_minutes, (1, 2, 5, 10, 15, 30, 60)),
            ('自动下线并重查，每', app.auto_offline, app.offline_minutes, (1, 5, 10, 15, 30, 60, 120, 180, 360))]):
            ttk.Checkbutton(timers, text=text, variable=enabled, style='Compact.TCheckbutton',
                            command=lambda flag=enabled: app.timer_changed(flag)).grid(row=i, column=0, sticky='w', pady=3)
            box = ttk.Combobox(timers, textvariable=minutes, values=choices, state='readonly',
                               width=6, style='Compact.TCombobox')
            box.grid(row=i, column=1, padx=(12, 8), pady=3)
            box.bind('<<ComboboxSelected>>', lambda _: app.timer_changed())
            self.label(timers, '分钟').grid(row=i, column=2, sticky='w')
        self.countdown_label = self.label(self.body, variable=app.countdown, size=9, wrap=520)
        self.countdown_label.pack(anchor='w', pady=(6, 0))

        self.section('账号登录')
        form = self.row(self.body)
        form.columnconfigure(1, weight=1)
        self.entries = {}
        for i, (name, variable, secret) in enumerate([('学号', app.user, False), ('密码', app.password, True), ('验证码', app.code, False)]):
            self.label(form, name).grid(row=i, column=0, sticky='w', padx=(0, 16), pady=3)
            entry = ttk.Entry(form, textvariable=variable, show='•' if secret else '', style='Compact.TEntry', width=20)
            entry.grid(row=i, column=1, sticky='ew', pady=3)
            self.entries[name] = entry
        app.captcha_label = tk.Label(form, text='验证码未获取', font=(FONT, 9), fg=COLORS['muted'],
                                     bg=COLORS['secondary'], width=17, height=2)
        app.captcha_label.grid(row=2, column=2, padx=(12, 0), sticky='nsew', pady=3)
        form.columnconfigure(2, minsize=140)
        self.entries['验证码'].bind('<Return>', lambda _: app.login())
        choices = self.row(self.body)
        choices.pack_configure(pady=(4, 0))
        ttk.Checkbutton(choices, text='记住账号', variable=app.remember_user, style='Compact.TCheckbutton',
                        command=lambda: app.credentials_changed('user')).pack(side='left', padx=(0, 12))
        ttk.Checkbutton(choices, text='保存密码（Windows 加密）', variable=app.remember_password,
                        style='Compact.TCheckbutton', command=lambda: app.credentials_changed('password')).pack(side='left')
        login_actions = self.row(self.body)
        login_actions.pack_configure(pady=(8, 0))
        self.captcha_button = self.button(login_actions, '获取 / 更换验证码', lambda: app.submit('captcha'), width=19)
        self.captcha_button.pack(side='left', padx=(0, 8))
        self.login_button = self.button(login_actions, '登录', app.login, width=8)
        self.login_button.pack(side='left')
        self.hint_label = self.label(self.body, variable=self.login_hint, size=9, wrap=520)
        self.hint_label.pack(anchor='w', pady=(8, 0))

        self.warning = self.label(self.body,
            '在线用量可能尚未结算。下线会断开账号下的在线设备。\n下线后自动查询约 6 秒；最终仍以服务器结算为准。',
            size=9, color=COLORS['danger'], wrap=520)
        self.warning.pack(anchor='w', pady=(14, 0))

        footer = tk.Frame(self.root, bg=COLORS['secondary'], padx=24, pady=10)
        footer.pack(fill='x')
        self.status_label = self.label(footer, variable=app.status, size=9, wrap=550, bg=COLORS['secondary'])
        self.status_label.pack(fill='x', anchor='w')
        footer.bind('<Configure>', lambda e: self.status_label.configure(wraplength=max(250, e.width-48)))
        self.progress_slot = tk.Frame(self.root, bg=COLORS['background'], height=3)
        self.progress_slot.pack(fill='x')
        self.progress_slot.pack_propagate(False)
        self.progress = ttk.Progressbar(self.progress_slot, style='Compact.Horizontal.TProgressbar', mode='indeterminate')
        self.root.bind('<Control-r>', lambda _: app.submit('home'))

    def label(self, parent, text=None, variable=None, size=10, bold=False, color=None, wrap=0, bg=None):
        return tk.Label(parent, text=text, textvariable=variable, font=(FONT, size, 'bold' if bold else 'normal'),
                        bg=bg or COLORS['background'], fg=color or COLORS['muted' if size <= 9 else 'text'],
                        justify='left', anchor='w', wraplength=wrap)

    def row(self, parent):
        frame = tk.Frame(parent, bg=COLORS['background'])
        frame.pack(fill='x')
        return frame

    def button(self, parent, text, command, style='Compact.TButton', width=None):
        button = ttk.Button(parent, text=text, command=command, style=style, width=width, takefocus=True)
        self.app.buttons.append(button)
        return button

    def section(self, title):
        tk.Frame(self.body, bg=COLORS['line'], height=1).pack(fill='x', pady=(12, 8))
        self.label(self.body, title, size=11, bold=True).pack(anchor='w', pady=(0, 6))

    def resize(self, event=None):
        self.canvas.itemconfigure(self.body_window, width=self.canvas.winfo_width())
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))
        box = self.canvas.bbox('all')
        needed = box and box[3] > self.canvas.winfo_height()+1
        if needed and not self.scroll.winfo_manager():
            self.scroll.pack(side='right', fill='y')
        elif not needed and self.scroll.winfo_manager():
            self.scroll.pack_forget()
            self.canvas.yview_moveto(0)
        wrap = max(250, self.canvas.winfo_width()-48)
        for widget in (getattr(self, 'hint_label', None), getattr(self, 'countdown_label', None), getattr(self, 'warning', None)):
            if widget:
                widget.configure(wraplength=wrap)

    def wheel(self, event):
        if self.scroll.winfo_manager():
            self.canvas.yview_scroll(-int(event.delta / 120), 'units')

    def focus_visible(self, event):
        try:
            if str(event.widget).startswith(str(self.body)):
                y = event.widget.winfo_rooty()-self.canvas.winfo_rooty()
                if y < 0 or y+event.widget.winfo_height() > self.canvas.winfo_height():
                    total = max(1, self.canvas.bbox('all')[3])
                    self.canvas.yview_moveto(max(0, (self.canvas.canvasy(0)+y-12)/total))
        except tk.TclError:
            pass

    def set_busy(self, busy):
        if busy:
            self.connection_label.configure(fg=COLORS['muted'])
            self.connection.set({'home': '正在查询', 'captcha': '正在获取验证码',
                                 'offline': '正在下线并重查', 'login': '正在登录', 'sms': '正在登录'}.get(self.app.active_command, '正在处理'))
            self.progress.place(x=0, y=0, relwidth=1, height=3)
            self.progress.start(18)
        else:
            self.progress.stop()
            self.progress.place_forget()
            if self.connection.get().startswith('正在'):
                self.connection.set('已登录' if self.app.authenticated else '等待登录')
        self.refresh.configure(text='刷新中…' if busy and self.app.active_command == 'home' else '刷新余量')
        self.captcha_button.configure(text='获取中…' if busy and self.app.active_command == 'captcha' else '获取 / 更换验证码')
        self.login_button.configure(text='登录中…' if busy and self.app.active_command in ('login', 'sms') else '登录')

    def success(self):
        self.last_update = time.strftime('%H:%M:%S')
        self.updated.set('更新于 ' + self.last_update)
        self.connection.set('已登录')
        self.connection_label.configure(fg=COLORS['accent'])
        self.set_hint('当前会话有效，无需重新登录。')

    def set_hint(self, message, error=False):
        self.login_hint.set(message)
        self.hint_label.configure(fg=COLORS['danger' if error else 'muted'])

    def error(self, message, expired=False):
        self.connection.set('需要登录' if expired else '操作失败')
        self.connection_label.configure(fg=COLORS['danger'])
        if self.last_update:
            self.updated.set('上次更新 ' + self.last_update)
        if expired or self.app.active_command in ('login', 'sms', 'captcha'):
            self.set_hint(message, error=True)
