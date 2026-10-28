import sys
from pathlib import Path
from unittest.mock import Mock
import tempfile
import base64
import requests
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from api_app import Client, Store, parse_home
test_dir = tempfile.TemporaryDirectory()
store = Store(test_dir.name)

home = '<table><tr><th>已用流量</th><th>计费流量剩余(不含套餐)</th></tr><tr><td>12.500G</td><td>8.250G</td></tr></table>'
key = rsa.generate_private_key(public_exponent=65537, key_size=1024)
pem = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
login = '<meta name="csrf-token" content="test-token"><meta name="csrf-param" content="_csrf-8800"><input id="public" value="' + pem + '"><input id="loginform-password"><img id="loginform-verifycode-image" src="/site/captcha?v=test">'
calls = []
def request(method, url, **kwargs):
    path = url.replace('https://zfw.buaa.edu.cn', '')
    calls.append((method, path, kwargs))
    r = requests.Response()
    r.status_code = 200
    r.encoding = 'utf-8'
    content = login if path == '/' and method == 'GET' else home
    if path == '/site/captcha?v=test': content = 'image-bytes'
    if path == '/site/validate-user':
        form = kwargs['data']
        assert form['_csrf-8800'] == 'test-token'
        assert key.decrypt(base64.b64decode(form['LoginForm[password]']), padding.PKCS1v15()) == b'test-password'
        content = '{"success":true,"inputSms":false}'
    r._content = content.encode()
    return r

c = Client(store)
c.session.request = request
assert c.captcha() == b'image-bytes'
assert c.login('test-user', 'test-password', 'test-code')[1][0]['已用流量'] == '12.500G'
assert [(m,p) for m,p,k in calls] == [('GET','/'),('GET','/site/captcha?v=test'),('POST','/site/validate-user'),('POST','/'),('GET','/home')]
try: parse_home(login)
except ValueError as e: assert '登录已失效' in str(e)
else: raise AssertionError('must reject login page')
assert c.session.verify is True
print('PASS: CAPTCHA/session request order, RSA encryption, CSRF, homepage parsing, expired login rejection, TLS validation')

from bs4 import BeautifulSoup
from unittest.mock import patch
c.soup = BeautifulSoup('<meta name="csrf-token" content="t"><meta name="csrf-param" content="p"><a href="/home/onekey" data-method="post">一键下线</a>', 'html.parser')
c.home = Mock(return_value=parse_home(home))
c.request = Mock(return_value=None)
with patch('api_app.time.sleep'):
    assert c.offline()[0]['已用流量'] == '12.500G'
assert c.request.call_count == 1
assert c.request.call_args.args == ('POST', '/home/onekey')
assert c.home.call_count == 4
c.request = Mock(side_effect=requests.Timeout('test'))
try: c.offline()
except ValueError as e: assert '不会重复提交' in str(e)
else: raise AssertionError('must expose uncertain result')
assert c.request.call_count == 1
print('PASS: one-time offline POST, subsequent read-only polls, no destructive retry on timeout')

import tkinter as tk
from api_app import App
root = tk.Tk()
app = App(root, store=store, start_worker=False)
root.update()
assert len(app.buttons) == 4
root.destroy()
print('PASS: API desktop window starts')
