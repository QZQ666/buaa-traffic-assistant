import sys
import tempfile
from pathlib import Path
import tkinter as tk

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from api_app import App, Store
from desktop_ui import COLORS


def luminance(color):
    channels = [int(color[i:i+2], 16) / 255 for i in (1, 3, 5)]
    channels = [x / 12.92 if x <= .04045 else ((x+.055)/1.055)**2.4 for x in channels]
    return sum(a*b for a, b in zip(channels, (.2126, .7152, .0722)))


for fg, bg in [('text', 'surface'), ('muted', 'surface'), ('muted', 'background'), ('mint', 'hero'), ('hero_muted', 'hero'), ('danger', 'danger_soft')]:
    a, b = sorted((luminance(COLORS[fg]), luminance(COLORS[bg])))
    assert (b+.05)/(a+.05) >= 4.5, (fg, bg)
assert (1.05)/(luminance(COLORS['accent'])+.05) >= 4.5
print('PASS: semantic text and action color pairs meet 4.5:1')

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
    print('PASS: empty login validation blocks network jobs and identifies missing field')
    for geometry in ('1040x850', '900x620'):
        root.geometry(geometry)
        root.update()
        app.view.canvas.yview_moveto(0)
        root.update()
        region = app.view.canvas.bbox('all')
        assert region[2] <= app.view.canvas.winfo_width() + 1
        for button in app.buttons:
            # Every action remains within the scrollable canvas, with no horizontal clipping.
            x = button.winfo_rootx() - app.view.canvas.winfo_rootx()
            assert x >= 0 and x + button.winfo_width() <= region[2]
        app.status.set('操作失败，已有数据可能过时。' * 8)
        root.update()
        assert app.view.status_label.winfo_y() >= 0
    print('PASS: desktop and compact layouts retain all controls without horizontal overflow')
    app.submit('home')
    root.update()
    assert app.busy and all(str(button['state']) == 'disabled' for button in app.buttons)
    app.results.put(('idle', None))
    app.poll()
    assert not app.busy and not app.view.progress.winfo_manager()
    root.destroy()
    print('PASS: async loading disables actions and removes progress after completion')
