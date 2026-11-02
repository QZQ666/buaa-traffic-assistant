import sys
import tempfile
from pathlib import Path
import tkinter as tk
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from api_app import App, Store, friendly_error
from compact_ui import COLORS


def light(color):
    values = [int(color[i:i+2], 16)/255 for i in (1, 3, 5)]
    values = [v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in values]
    return sum(a*b for a, b in zip(values, (.2126, .7152, .0722)))


for foreground, background in [('text', 'background'), ('muted', 'background'),
                               ('muted', 'secondary'), ('danger', 'background'),
                               ('accent', 'background')]:
    lo, hi = sorted([light(COLORS[foreground]), light(COLORS[background])])
    assert (hi+.05)/(lo+.05) >= 4.5
assert 1.05/(light(COLORS['accent'])+.05) >= 4.5
assert '超时' in friendly_error(requests.Timeout('synthetic transport internals'))
assert 'synthetic' not in friendly_error(requests.Timeout('synthetic transport internals'))
print('PASS: text/action contrast and actionable timeout copy')

with tempfile.TemporaryDirectory() as directory:
    root = tk.Tk()
    app = App(root, store=Store(directory), start_worker=False)
    root.update()
    app.login()
    assert app.jobs.empty() and '学号' in app.view.login_hint.get()
    app.user.set('test-user')
    app.login()
    assert app.jobs.empty() and '密码' in app.view.login_hint.get()
    app.password.set('test-password')
    app.login()
    assert app.jobs.empty() and '验证码' in app.view.login_hint.get()

    app.results.put(('data', [{'已用流量': '12.500G', '免费流量剩余': '0byte',
                              '计费流量剩余': '8.250G', '结算日期': '2026-12-01'}]))
    app.poll()
    assert app.authenticated and app.view.connection.get() == '已登录'
    assert '更新于' in app.view.updated.get()
    print('PASS: empty form validation and actual result state')

    for size in ('620x760', '560x620'):
        root.geometry(size)
        root.update()
        app.view.canvas.yview_moveto(0)
        root.update()
        region = app.view.canvas.bbox('all')
        assert region[2] <= app.view.canvas.winfo_width()+1
        for button in app.buttons:
            x = button.winfo_rootx()-app.view.canvas.winfo_rootx()
            assert x >= 0 and x+button.winfo_width() <= region[2]
        app.status.set('网络连接超时，请确认官网可访问后重试。' * 4)
        root.update()
        app.view.entries['验证码'].event_generate('<FocusIn>')
        root.update()
        y = app.view.entries['验证码'].winfo_rooty()-app.view.canvas.winfo_rooty()
        assert y >= 0 and y+app.view.entries['验证码'].winfo_height() <= app.view.canvas.winfo_height()
    print('PASS: compact layout and focused control remains reachable with long error text')

    app.submit('home')
    assert app.busy and all(str(b['state']) == 'disabled' for b in app.buttons)
    assert '刷新中' in app.view.refresh['text']
    app.results.put(('error', friendly_error(requests.Timeout())))
    app.results.put(('idle', None))
    app.poll()
    assert not app.busy and app.view.connection.get() == '操作失败'
    assert app.view.updated.get().startswith('上次更新')
    assert not app.view.progress.winfo_manager()
    root.destroy()
    print('PASS: loading, error recovery and stale-data indication')
