# 北航校园网流量助手

Windows 桌面小工具，通过北航校园网自助服务平台的 HTTPS 请求查询余量，无需启动浏览器。当前版本为 2.1.1，保留 2.1 界面。

2.1.1 限制请求跳转只能发生在学校 HTTPS 域名内，更新网络依赖，并移除不必要的 Pillow 图像依赖；验证码使用原生 Tk 显示。下载请使用最新 Release，旧版 2.1.0 的安装包已撤下。隐私与安全说明见 [SECURITY.md](SECURITY.md)。

## 功能

- 在工具内手动填写学号、密码、图形验证码，支持短信验证分支。
- 显示计费流量剩余、免费流量剩余、已用流量及结算日期。
- 自动保存并尝试恢复本机 Cookie；会话有效时无需再次登录。
- 账号和密码分别选择是否保存，密码与 Cookie 使用 Windows DPAPI 加密。
- 下拉选择自动刷新间隔，以及独立的自动下线并重查间隔，显示倒计时并保留设置。
- 下线请求仅提交一次；请求失败时停止自动下线，避免重复断网。

## 运行

需要 Windows、Python 3.10 或更新版本及可访问校园网自助服务平台的网络。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe api_app.py
```

启动会尝试复用 Cookie。首次使用或会话失效时，点击“获取 / 更换验证码”，填写登录信息后登录。验证码由使用者手动填写。

勾选“记住账号”和“保存密码”后，登录或关闭程序时保存输入值。取消勾选会清除对应保存值；取消记住账号会同时取消保存密码。

## 定时查询与结算

自动刷新可选 1、2、5、10、15、30、60 分钟。自动下线可选 1、5、10、15、30、60、120、180、360 分钟，默认关闭，开启时需要确认断网影响。

**一键下线会断开此账号下的在线设备，包括运行工具的设备。工具不会自动重新连接校园网。** 下线结束在线会话并触发服务器结算，不会清零本月用量或增加套餐额度。

下线后间隔两秒查询三次，请求耗时另计；服务器结算可能延迟。若本机断网，先重新联网，再刷新余量。

定时任务只在程序运行且已登录时执行；登录失效时等待重新登录。自动下线失败后关闭该任务，检查网络后可重新启用。设置重启后保留，恢复登录成功后开始倒计时，不会启动即下线。

## 本地数据与隐私

应用数据保存在 `%LOCALAPPDATA%\BuaaTraffic`：

| 文件 | 内容 |
| --- | --- |
| `session.dpapi` | Windows DPAPI 加密的会话 Cookie |
| `credentials.dpapi` | 按用户选项保存的加密账号、密码 |
| `settings.json` | 保存选项及定时间隔，无账号密码 |

DPAPI 数据可由当前 Windows 用户解密，请勿分享会话或凭据文件。密码仅发送到学校登录服务；应用没有遥测或第三方上传功能。

仓库只包含源码、依赖、说明及虚构数据的测试。`.gitignore` 排除了运行数据、加密凭据、Cookie、截图、抓包记录、网页和构建产物。

## 构建 EXE

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller==6.20.0
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --onefile --windowed --name BuaaTrafficAPI_2.1.1 api_app.py
```

结果在 `dist/BuaaTrafficAPI_2.1.1.exe`。打包文件没有加入 Git 源码，发布包放在 Releases。

## 验证

在 Windows 上运行：

```powershell
python tests/test_api.py
python tests/test_persistence_timers.py
python tests/test_request_security.py
```

测试使用虚构账号、会话和用量，不访问真实账号、不执行真实下线。覆盖 RSA 加密、CSRF 提交、表格解析、DPAPI 保存恢复、账号密码保存选项、定时任务优先级、防重入及错误暂停。

## 协议与限制

应用使用 `https://zfw.buaa.edu.cn` 当前网页采用的内部 HTTP 协议，不是学校承诺稳定的公开 API。登录使用页面提供的 RSA 公钥和 CSRF，读取 `GET /home` 的产品表，下线使用 `POST /home/onekey`。

页面或协议变更可能需要更新程序。Cookie 是否继续有效取决于服务器；程序无法保证永久免登录。多个产品时当前显示第一个产品。程序直连学校站点，不继承环境代理。
