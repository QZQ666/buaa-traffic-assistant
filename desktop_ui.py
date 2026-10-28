"""Desktop view: native Tk controls with a quiet, accessible visual hierarchy."""
import tkinter as tk
from tkinter import ttk

COLORS = {
    'background': '#F2F5F8', 'surface': '#FFFFFF', 'text': '#152D3A',
    'muted': '#526574', 'line': '#DCE4EA', 'accent': '#087F72',
    'accent_hover': '#06695F', 'hero': '#142F3B', 'hero_muted': '#B8CCD4',
    'mint': '#83E7D2', 'soft': '#EDF7F4', 'danger': '#A8342D',
    'danger_soft': '#FFF3EF', 'disabled': '#657785',
}
FONT = 'Microsoft YaHei UI'


class DesktopView:
    def __init__(self, app):
        self.app, self.root = app, app.root
        self.root.configure(bg=COLORS['background'])
        self.icon = tk.PhotoImage(width=32, height=32)
        self.icon.put(COLORS['accent'], to=(0, 0, 32, 32))
        for x, top in [(8, 20), (15, 14), (22, 7)]:
            self.icon.put('white', to=(x, top, x+3, 26))
        self.root.iconphoto(True, self.icon)
        self.root.option_add('*Font', (FONT, 10))
        self.style = ttk.Style(self.root)
        self.style.theme_use('clam')
        self.style.configure('Primary.TButton', font=(FONT, 10, 'bold'), padding=(18, 11),
                             background=COLORS['accent'], foreground='white', borderwidth=0,
                             focusthickness=2, focuscolor=COLORS['text'])
        self.style.map('Primary.TButton', background=[('disabled', '#DCE4EA'), ('pressed', '#05574F'), ('active', COLORS['accent_hover'])],
                       foreground=[('disabled', COLORS['disabled'])])
        self.style.configure('Secondary.TButton', font=(FONT, 10), padding=(12, 10),
                             background='#E9EEF2', foreground=COLORS['text'], borderwidth=0,
                             focusthickness=2, focuscolor=COLORS['accent'])
        self.style.map('Secondary.TButton', background=[('disabled', '#EDF0F3'), ('active', '#DCE5EC')],
                       foreground=[('disabled', COLORS['disabled'])])
        self.style.configure('Danger.TButton', font=(FONT, 10), padding=(12, 10),
                             background=COLORS['danger_soft'], foreground=COLORS['danger'], borderwidth=0,
                             focusthickness=2, focuscolor=COLORS['danger'])
        self.style.map('Danger.TButton', background=[('disabled', '#EDF0F3'), ('active', '#FBE0D8')],
                       foreground=[('disabled', COLORS['disabled'])])
        self.style.configure('TEntry', padding=(9, 8), fieldbackground='white', bordercolor='#8799A6',
                             lightcolor='#8799A6', darkcolor='#8799A6', foreground=COLORS['text'])
        self.style.map('TEntry', bordercolor=[('focus', COLORS['accent'])], lightcolor=[('focus', COLORS['accent'])], darkcolor=[('focus', COLORS['accent'])])
        self.style.configure('TCombobox', padding=(8, 8), foreground=COLORS['text'], bordercolor='#8799A6', arrowsize=14)
        self.style.map('TCombobox', fieldbackground=[('readonly', 'white')], foreground=[('readonly', COLORS['text'])], selectbackground=[('readonly', 'white')], selectforeground=[('readonly', COLORS['text'])])
        self.style.configure('TCheckbutton', background='white', foreground=COLORS['text'], padding=(0, 6), font=(FONT, 10))
        self.style.map('TCheckbutton', background=[('active', 'white')])
        self.style.configure('Work.Horizontal.TProgressbar', background=COLORS['accent'], troughcolor=COLORS['background'], borderwidth=0)

        header = tk.Frame(self.root, bg=COLORS['background'])
        header.pack(fill='x', padx=28, pady=(16, 12))
        mark = tk.Canvas(header, width=42, height=42, bg=COLORS['background'], highlightthickness=0)
        mark.pack(side='left', padx=(0, 12))
        mark.create_rectangle(1, 1, 41, 41, fill=COLORS['accent'], outline='')
        for x, y, height in [(11, 28, 8), (20, 28, 15), (29, 28, 22)]:
            mark.create_line(x, y, x, y-height, fill='white', width=4)
        title = tk.Frame(header, bg=COLORS['background'])
        title.pack(side='left')
        self.label(title, '校园网助手', size=20, bold=True, bg=COLORS['background']).pack(anchor='w')
        self.label(title, '北航校园网  /  流量与会话管理', size=9, muted=True, bg=COLORS['background']).pack(anchor='w', pady=(3, 0))
        self.connection = tk.StringVar(value='等待连接')
        self.label(header, variable=self.connection, size=10, color=COLORS['accent'], bg=COLORS['background']).pack(side='right')
        self.progress_slot = tk.Frame(self.root, height=3, bg=COLORS['background'])
        self.progress_slot.pack(fill='x', padx=28)
        self.progress_slot.pack_propagate(False)
        self.progress = ttk.Progressbar(self.progress_slot, style='Work.Horizontal.TProgressbar', mode='indeterminate', maximum=100)

        shell = tk.Frame(self.root, bg=COLORS['background'])
        shell.pack(fill='both', expand=True, padx=24, pady=(12, 0))
        self.canvas = tk.Canvas(shell, bg=COLORS['background'], highlightthickness=0)
        scroll = ttk.Scrollbar(shell, orient='vertical', command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scroll.set)
        self.canvas.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        body = tk.Frame(self.canvas, bg=COLORS['background'])
        self.window = self.canvas.create_window(0, 0, window=body, anchor='nw')
        body.bind('<Configure>', lambda _: self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>', lambda e: self.canvas.itemconfigure(self.window, width=e.width))
        self.root.bind('<MouseWheel>', self.wheel, add='+')
        self.root.bind('<FocusIn>', self.focus_visible, add='+')
        body.columnconfigure(0, weight=6, uniform='columns')
        body.columnconfigure(1, weight=5, uniform='columns')
        left = tk.Frame(body, bg=COLORS['background'])
        left.grid(row=0, column=0, sticky='nsew', padx=(4, 10), pady=4)
        right = tk.Frame(body, bg=COLORS['background'])
        right.grid(row=0, column=1, sticky='nsew', padx=(10, 4), pady=4)

        hero = tk.Frame(left, bg=COLORS['hero'], padx=24, pady=16)
        hero.pack(fill='x')
        self.label(hero, '计费流量剩余', size=11, color=COLORS['hero_muted'], bg=COLORS['hero']).pack(anchor='w')
        self.label(hero, variable=app.remaining, size=38, bold=True, color=COLORS['mint'], bg=COLORS['hero']).pack(anchor='w', pady=(4, 4))
        self.updated = tk.StringVar(value='等待首次查询')
        self.label(hero, variable=self.updated, size=9, color=COLORS['hero_muted'], bg=COLORS['hero']).pack(anchor='w')
        self.label(hero, '在线用量可能尚未结算，以网站记录为准。', size=9, color=COLORS['hero_muted'], bg=COLORS['hero']).pack(anchor='w', pady=(8, 0))
        stats = self.card(left)
        stats.pack(fill='x', pady=(0, 12))
        self.used = tk.StringVar(value='—')
        self.free = tk.StringVar(value='—')
        self.settlement = tk.StringVar(value='—')
        for i, (name, variable) in enumerate([('已用流量', self.used), ('免费剩余', self.free), ('结算日期', self.settlement)]):
            part = tk.Frame(stats, bg='white')
            part.grid(row=0, column=i, sticky='nsew', padx=(0 if i == 0 else 12, 0))
            stats.columnconfigure(i, weight=1)
            self.label(part, name, size=9, muted=True).pack(anchor='w')
            self.label(part, variable=variable, size=12, bold=True).pack(anchor='w', pady=(6, 0))
        self.refresh = self.button(stats, '刷新余量', lambda: app.submit('home'), 'Primary.TButton')
        self.refresh.grid(row=1, column=0, columnspan=3, sticky='ew', pady=(12, 0))

        login = self.card(left)
        login.pack(fill='x', pady=(0, 8))
        self.label(login, '账号与登录', size=14, bold=True).grid(row=0, column=0, columnspan=2, sticky='w')
        self.label(login, '会话有效时自动恢复；失效后填写验证码登录。', size=9, muted=True).grid(row=1, column=0, columnspan=2, sticky='w', pady=(4, 8))
        login.columnconfigure(0, weight=1, uniform='login')
        login.columnconfigure(1, weight=1, uniform='login')
        self.entries = {}
        for column, (name, variable, secret) in enumerate([('学号', app.user, False), ('密码', app.password, True)]):
            block = tk.Frame(login, bg='white')
            block.grid(row=2, column=column, sticky='ew', padx=(0, 8) if column == 0 else (8, 0))
            self.label(block, name, size=10).pack(anchor='w', pady=(0, 5))
            entry = ttk.Entry(block, textvariable=variable, show='•' if secret else '', width=12)
            entry.pack(fill='x')
            self.entries[name] = entry
        verification = tk.Frame(login, bg='white')
        verification.grid(row=3, column=0, columnspan=2, sticky='ew', pady=(8, 0))
        verification.columnconfigure(0, weight=1)
        self.label(verification, '图形验证码', size=10).grid(row=0, column=0, sticky='w', pady=(0, 5))
        code = ttk.Entry(verification, textvariable=app.code, width=10)
        code.grid(row=1, column=0, sticky='ew')
        code.bind('<Return>', lambda _: app.login())
        self.entries['验证码'] = code
        app.captcha_label = tk.Label(verification, text='验证码未获取', font=(FONT, 9), fg=COLORS['muted'], bg='#F2F5F8', width=16, height=2)
        app.captcha_label.grid(row=1, column=1, padx=(12, 0))
        checks = tk.Frame(login, bg='white')
        checks.grid(row=4, column=0, columnspan=2, sticky='w', pady=(8, 0))
        ttk.Checkbutton(checks, text='记住账号', variable=app.remember_user, command=lambda: app.credentials_changed('user')).pack(side='left', padx=(0, 12))
        ttk.Checkbutton(checks, text='加密保存密码', variable=app.remember_password, command=lambda: app.credentials_changed('password')).pack(side='left')
        self.login_hint = tk.StringVar(value='')
        self.label(login, variable=self.login_hint, size=9, color=COLORS['danger'], wrap=390).grid(row=5, column=0, columnspan=2, sticky='w')
        self.button(login, '获取验证码', lambda: app.submit('captcha')).grid(row=6, column=0, sticky='ew', padx=(0, 8), pady=(8, 0))
        self.button(login, '登录账号', app.login).grid(row=6, column=1, sticky='ew', padx=(8, 0), pady=(8, 0))

        automation = self.card(right)
        automation.pack(fill='x', pady=(0, 16))
        self.label(automation, '自动化设置', size=14, bold=True).pack(anchor='w')
        self.label(automation, '登录后开始计时，设置自动保留。', size=9, muted=True).pack(anchor='w', pady=(4, 18))
        self.timer_block(automation, '自动刷新', '定时读取网站余量，不影响在线设备。', app.auto, app.refresh_minutes, (1, 2, 5, 10, 15, 30, 60))
        tk.Frame(automation, bg=COLORS['line'], height=1).pack(fill='x', pady=18)
        self.timer_block(automation, '自动下线并重查', '结束在线会话，等待网站结算后查询。', app.auto_offline, app.offline_minutes, (1, 5, 10, 15, 30, 60, 120, 180, 360))
        warning = tk.Frame(automation, bg=COLORS['danger_soft'], padx=12, pady=12)
        warning.pack(fill='x', pady=(16, 0))
        self.label(warning, '会断开此账号下的在线设备', size=10, bold=True, color=COLORS['danger'], bg=COLORS['danger_soft']).pack(anchor='w')
        self.label(warning, '包括当前电脑；工具不会自动重新联网。', size=9, color=COLORS['danger'], bg=COLORS['danger_soft'], wrap=300).pack(anchor='w', pady=(4, 0))
        self.button(automation, '立即下线并重查…', app.offline, 'Danger.TButton').pack(fill='x', pady=(14, 0))

        schedule = self.card(right)
        schedule.pack(fill='x', pady=(0, 16))
        self.label(schedule, '任务状态', size=12, bold=True).pack(anchor='w')
        self.label(schedule, variable=app.countdown, size=10, wrap=320).pack(anchor='w', pady=(10, 0))
        self.label(schedule, '程序关闭时不会执行任务。', size=9, muted=True).pack(anchor='w', pady=(10, 0))
        privacy = tk.Frame(right, bg=COLORS['background'], padx=6)
        privacy.pack(fill='x')
        self.label(privacy, '本机加密保存', size=10, bold=True, bg=COLORS['background']).pack(anchor='w')
        self.label(privacy, '账号密码按你的选择保留。会话失效仍需验证码登录；查询数据仅来自学校站点。', size=9, muted=True, bg=COLORS['background'], wrap=330).pack(anchor='w', pady=(6, 8))

        footer = tk.Frame(self.root, bg=COLORS['background'])
        footer.pack(fill='x', padx=28, pady=(10, 12))
        self.status_label = self.label(footer, variable=app.status, size=9, muted=True, bg=COLORS['background'], wrap=880)
        self.status_label.pack(side='left', fill='x', expand=True, anchor='w')
        self.label(footer, 'v2.2', size=9, muted=True, bg=COLORS['background']).pack(side='right', padx=(12, 0))
        footer.bind('<Configure>', lambda e: self.status_label.configure(wraplength=max(300, e.width-65)))
        self.root.bind('<Control-r>', lambda _: app.submit('home'))

    def label(self, parent, text=None, variable=None, size=10, bold=False, muted=False, color=None, bg='white', wrap=0):
        return tk.Label(parent, text=text, textvariable=variable, font=(FONT, size, 'bold' if bold else 'normal'),
                        fg=color or COLORS['muted' if muted else 'text'], bg=bg, anchor='w', justify='left', wraplength=wrap)

    def card(self, parent):
        return tk.Frame(parent, bg='white', padx=20, pady=14, highlightbackground=COLORS['line'], highlightthickness=1)

    def button(self, parent, text, command, style='Secondary.TButton'):
        button = ttk.Button(parent, text=text, command=command, style=style, cursor='hand2', takefocus=True)
        self.app.buttons.append(button)
        return button

    def timer_block(self, parent, name, description, enabled, minutes, choices):
        ttk.Checkbutton(parent, text=name, variable=enabled, command=lambda: self.app.timer_changed(enabled)).pack(anchor='w')
        self.label(parent, description, size=9, muted=True, wrap=320).pack(anchor='w', pady=(2, 10))
        row = tk.Frame(parent, bg='white')
        row.pack(fill='x')
        self.label(row, '每', size=10).pack(side='left', padx=(0, 10))
        box = ttk.Combobox(row, textvariable=minutes, values=choices, state='readonly', width=7, takefocus=True)
        box.pack(side='left')
        box.bind('<<ComboboxSelected>>', lambda _: self.app.timer_changed())
        self.label(row, '分钟执行一次', size=10).pack(side='left', padx=(10, 0))

    def wheel(self, event):
        if self.canvas.bbox('all') and self.canvas.bbox('all')[3] > self.canvas.winfo_height():
            self.canvas.yview_scroll(-int(event.delta / 120), 'units')

    def focus_visible(self, event):
        widget = event.widget
        try:
            if str(widget).startswith(str(self.canvas)):
                top = widget.winfo_rooty() - self.canvas.winfo_rooty()
                height = self.canvas.winfo_height()
                if top < 0 or top + widget.winfo_height() > height:
                    total = max(1, self.canvas.bbox('all')[3])
                    self.canvas.yview_moveto(max(0, (self.canvas.canvasy(0) + top - 20) / total))
        except tk.TclError:
            pass

    def set_busy(self, busy):
        if busy:
            self.progress.place(x=0, y=0, relwidth=1, height=3)
            self.progress.start(14)
        else:
            self.progress.stop()
            self.progress.place_forget()
        self.refresh.configure(text='查询中…' if busy and self.app.active_command == 'home' else '刷新余量')

    def show_record(self, record, timestamp):
        def value(data, label):
            return next((v for k, v in data.items() if label in k), '—')
        self.used.set(value(record, '已用流量'))
        self.free.set(value(record, '免费流量剩余'))
        self.settlement.set(value(record, '结算日期'))
        self.updated.set('最近更新  ' + timestamp)
        self.connection.set('已登录 · 查询成功')
