import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch
import tkinter as tk
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from api_app import Client, Store, App

with tempfile.TemporaryDirectory() as directory:
    store = Store(directory)
    c = Client(store)
    c.session.cookies.set('PHPSESSID', 'fake-session', domain='zfw.buaa.edu.cn', path='/', secure=True)
    c.session.cookies.set('same', 'one', domain='zfw.buaa.edu.cn', path='/')
    c.session.cookies.set('same', 'two', domain='zfw.buaa.edu.cn', path='/home')
    c.save_session()
    assert not c.storage_notice
    raw = (Path(directory) / 'session.dpapi').read_bytes()
    assert b'fake-session' not in raw
    restored = Client(store)
    assert [(x.name,x.value,x.domain,x.path,x.secure) for x in restored.session.cookies] == [(x.name,x.value,x.domain,x.path,x.secure) for x in c.session.cookies]
    print('PASS: real Windows DPAPI cookie persistence and restart restoration, duplicate names and scope preserved')

    r = tk.Tk()
    app = App(r, store=store, start_worker=False)
    app.user.set('test-user')
    app.password.set('test-secret')
    app.remember_password.set(True)
    app.credentials_changed('password')
    assert app.remember_user.get()
    assert store.load('credentials.dpapi', {}, True)['password'] == 'test-secret'
    assert b'test-secret' not in (Path(directory) / 'credentials.dpapi').read_bytes()
    app.refresh_minutes.set('2')
    app.offline_minutes.set('15')
    app.auto.set(True)
    with patch('api_app.messagebox.askokcancel', return_value=True):
        app.auto_offline.set(True)
        app.timer_changed(app.auto_offline)
    app.close()

    r = tk.Tk()
    app = App(r, store=store, start_worker=False)
    assert app.user.get() == 'test-user' and app.password.get() == 'test-secret'
    assert app.refresh_minutes.get() == '2' and app.offline_minutes.get() == '15'
    assert app.auto.get() and app.auto_offline.get()
    print('PASS: opt-in encrypted credentials, interval settings survive restart')
    app.authenticated = True
    app.next_refresh = app.next_offline = time.monotonic() - 1
    app.tick()
    command, args = app.jobs.get_nowait()
    assert command == 'offline' and app.jobs.empty()
    app.tick()
    assert app.jobs.empty()  # busy suppresses overlap
    app.results.put(('error', 'test failure'))
    app.results.put(('idle', None))
    app.poll()
    assert not app.auto_offline.get()
    app.authenticated = False
    app.next_refresh = time.monotonic() - 1
    app.tick()
    assert app.jobs.empty()
    print('PASS: offline priority, no concurrent requests, error stops auto-offline, expired login pauses timers')
    app.remember_user.set(False)
    app.credentials_changed('user')
    assert not app.remember_password.get()
    assert store.load('credentials.dpapi', {}, True) == {'username':'', 'password':''}
    app.close()
    print('PASS: opting out deletes stored account and password values')

print('All regression checks passed')
