import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from api_app import Client, Store, captcha_image_data


def response(status=200, location=None):
    result = requests.Response()
    result.status_code = status
    result._content = b'ok'
    result._content_consumed = True
    if location:
        result.headers['Location'] = location
    return result


with tempfile.TemporaryDirectory() as directory:
    client = Client(Store(directory))
    for destination in ['https://example.invalid/collect', 'http://zfw.buaa.edu.cn/home',
                        '//example.invalid/collect', 'https://zfw.buaa.edu.cn:8443/home',
                        'https://name:password@zfw.buaa.edu.cn/home']:
        client.session.request = Mock(return_value=response(307, destination))
        try:
            client.request('POST', '/', data={'password': 'synthetic-test'})
        except ValueError:
            pass
        else:
            raise AssertionError('Unsafe redirect accepted')
        assert client.session.request.call_count == 1
        assert client.session.request.call_args.kwargs['allow_redirects'] is False
    print('PASS: cross-origin, HTTP downgrade, alternate port and URL credentials are blocked before forwarding')

    client.session.request = Mock(side_effect=[response(302, '/home'), response()])
    client.request('POST', '/', data={'password': 'synthetic-test'})
    second = client.session.request.call_args_list[1]
    assert second.args == ('GET', 'https://zfw.buaa.edu.cn/home')
    assert 'data' not in second.kwargs and client.session.verify is True
    client.session.request = Mock(side_effect=requests.Timeout())
    try:
        client.request('POST', '/home/onekey', data={})
    except requests.Timeout:
        pass
    assert client.session.request.call_count == 1
    print('PASS: normal login redirects work, TLS checks stay enabled and POST requests are never retried')

    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    original = tk.PhotoImage(width=120, height=40)
    original.put('white', to=(0, 0, 120, 40))
    raw = original.tk.call(str(original), 'data', '-format', 'png')
    loaded = tk.PhotoImage(data=captcha_image_data(raw))
    assert loaded.width() == 120 and loaded.height() == 40
    for invalid in [b'<html>error</html>', b'x' * (512*1024+1), b'\x89PNG\r\n\x1a\n' + b'x'*16]:
        try:
            captcha_image_data(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError('Invalid CAPTCHA accepted')
    root.destroy()
    print('PASS: native CAPTCHA display, format and image size bounds')
