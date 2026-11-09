# zhihuishuapi（delion智慧树）

基于 **PySide6 + Qt WebEngine** 的智慧树在线课程学习辅助工具，面向 Windows 桌面端。

客户端内置浏览器直接加载智慧树学习页面，登录后可读取课程、章节与视频列表，支持单个视频或批量队列上报学习进度；触发安全验证时自动跳转到验证页面，并提供基于 OpenCV 的滑块自动验证。

> 本仓库为**不完整开源版**：仅保留「刷课」链路，「刷题」等完整功能未包含，点击刷题按钮会提示前往完整版获取。

---

## 功能概览

| 功能 | 说明 |
| --- | --- |
| 内嵌浏览器 | QWebEngine 加载智慧树在线学习页，无需外部浏览器 |
| 扫码 / 手动登录 | 监听页面登录状态，登录成功后自动获取 Cookie 与用户信息 |
| 账号密码自动登录 | 从 `config.ini` 读取账号密码，自动填充、勾选协议并提交 |
| 滑块自动验证 | OpenCV 模板匹配定位缺口，JS 模拟鼠标轨迹拖动，最多尝试 3 次 |
| 课程列表 | 展示课程名称与学习进度，点击课程加载章节视频 |
| 视频清单 | 按章节折叠展示，标注「已完成 / 未完成」 |
| 单个刷课 | 点击视频条目直接上报该视频进度 |
| 批量刷课 | 勾选多个未完成视频（支持全选未完成），加入队列依次执行 |
| 实时进度 | 日志面板按 10 秒粒度输出当前秒数与百分比 |
| 安全验证恢复 | 上报失败自动打开验证页，轮询检测验证结束后返回刷课页 |
| 本地通信 | 内置页面与后端通过 `ws://127.0.0.1:9960/lesson` 通信，Token 握手校验 |
| 应用授权登录 | 打开授权网页，经本地回调端口换取长令牌，界面显示用户名 |

---

## 环境要求

- **操作系统**：Windows 10 / 11（UAC 提权、`ctypes.windll`、`Win32GUI` 打包均依赖 Windows）
- **Python**：3.10 及以上（PySide6 6.x 的要求，建议 3.11 / 3.12）
- **网络**：可访问智慧树站点及授权服务域名
- **依赖**：见 `requirements.txt`

| 依赖 | 用途 |
| --- | --- |
| PySide6 / PySide6-WebEngine | 桌面界面与内嵌浏览器 |
| qasync | 将 asyncio 事件循环接入 Qt |
| requests | 课程、视频、进度上报等 HTTP 接口 |
| opencv-python / numpy | 滑块缺口识别与图像处理 |
| aiohttp | 授权登录的本地回调 HTTP 服务 |
| websockets | 内置页面的本地 WebSocket 服务 |
| pycryptodome | 接口参数的 AES-CBC 加密 |

---

## 安装

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 运行

```powershell
python main.py
```

启动后主窗口加载智慧树在线学习首页。窗口默认 1400×700（最小 1000×600），左侧为浏览器区域，右侧为登录状态、操作按钮、账号配置与日志面板。

---

## 使用流程

### 1. 登录智慧树站点

刷课依赖智慧树站点的登录态（Cookie），共有两种方式：

**方式一：页面登录（扫码 / 账号密码）**

直接在左侧浏览器中完成智慧树登录。关闭自动登录开关时，客户端每 2 秒检测一次登录状态，最多等待 5 分钟；检测到登录成功后自动读取 Cookie、解析用户姓名，并在日志中提示「登录成功！请点击[刷课]按钮开始学习」。

**方式二：自动登录**

1. 在右侧「配置文件」中填写账户与密码，点击「保存」；
2. 打开「自动登录」开关（开关状态会写入 `config.ini`）；
3. 刷新页面后，客户端会等待登录表单就绪，自动填充账号密码、勾选隐私协议并点击登录；
4. 若出现滑块验证，自动进入滑块处理流程，最多尝试 3 次，失败则提示手动验证。

> 自动登录仅在页面处于登录页、且输入框为空时触发；已有登录态时不会重复提交。

### 2. 应用授权登录（可选）

右上角「登录」按钮打开授权网页，登录完成后通过本地 `http://127.0.0.1:19960/Software/token` 回调，将短令牌换取长令牌并保存到本地，界面显示「欢迎, 用户名」。

该授权状态与智慧树站点登录是**两套独立状态**：它只影响界面上的用户信息展示，刷课是否可用仍取决于智慧树 Cookie。

### 3. 刷课

1. 登录成功后点击右侧「刷课」；
2. 浏览器切换到内置页面，左栏列出课程名称与进度，右栏显示章节与视频；
3. 点击某门课程，加载该课程的章节与视频清单；
4. 单个视频：直接点击视频条目即开始上报；
5. 批量视频：勾选多个未完成视频（或点「全选未完成」），点击「开始刷课」，队列会逐个处理，页面显示全屏进度遮罩；
6. 队列结束后自动隐藏遮罩并刷新视频完成状态。

> 队列运行期间不支持再发起单个任务，避免同一账号并发上报。

### 4. 安全验证处理

上报接口返回失败时，客户端会：

1. 在日志中提示「上报失败，请解除当前验证」；
2. 自动跳转到该课程的智慧树学习页；
3. 每 2 秒检测验证弹窗是否消失，最多约 2 分钟；
4. 验证完成后自动返回刷课页面。

滑块验证由 `modules/slider_verify_async.py` 处理：下载背景图与拼图、Canny 边缘检测 + 模板匹配计算缺口位置，再通过 JS 派发鼠标事件模拟拖动。

### 5. 刷题

开源版不支持，点击后弹窗提示前往 `zhs.shaoxin.top` 获取完整功能。

---

## 配置说明

配置文件为项目根目录下的 `config.ini`（打包后位于 exe 同目录）：

```ini
[user]
account =
password =
auto_login_enabled = true
```

| 配置项 | 说明 |
| --- | --- |
| `account` | 智慧树账号（手机号 / 用户名） |
| `password` | 登录密码，**明文保存** |
| `auto_login_enabled` | 是否启用自动登录，`true` / `false` |

注意事项：

- 密码以明文写入 `config.ini`，请勿将填写过真实账号的配置文件提交到公开仓库；
- 代码中新建配置时默认值为 `false`，仓库自带的 `config.ini` 为 `true`；
- 修改后点击「保存」立即生效，无需重启。

---

## 目录结构

```text
x-zhs/
├─ main.py                       # 程序入口：注册 scheme、创建窗口、启动 qasync 事件循环
├─ build.py                      # cx_Freeze 打包脚本
├─ config.ini                    # 账号与自动登录配置
├─ app.manifest                  # Windows 清单：管理员权限、高 DPI
├─ requirements.txt
├─ assets/
│  ├─ delion.ico                 # 应用图标
│  └─ refresh.svg                # 刷新按钮图标
├─ components/
│  ├─ __init__.py
│  └─ main_window.py             # 主窗口、浏览器封装、登录/刷课/队列的业务编排
└─ modules/
    ├─ __init__.py                # 统一导出
    ├─ config.py                  # 应用级配置（窗口、URL、日志级别等）
    ├─ ini_config.py              # config.ini 读写
    ├─ logger.py                  # 控制台 + 文件日志
    ├─ web.py                     # 内置页面 HTML、自定义 scheme、WebSocket 服务
    ├─ auth.py                    # 授权长令牌的获取、刷新、存储
    ├─ auth_http_server.py        # 本地回调 HTTP 服务（127.0.0.1:19960）
    ├─ cookie_checker.py          # 通过页面 fetch / Cookie 判断智慧树登录态
    ├─ user.py                    # 获取用户真实姓名、uuid
    ├─ slider_verify_async.py     # 滑块验证：图像识别 + 轨迹模拟
    ├─ Access_to_public_courses.py # 课程列表接口（AES 加密请求）
    ├─ videos.py                  # 章节 / 视频清单与学习状态
    ├─ Report_progress.py         # 单个视频进度上报（核心上报逻辑）
    ├─ Line_up.py                 # 批量上报队列
    ├─ encryption.py              # AES-CBC/PKCS7 加解密工具
    ├─ uac_manager.py             # Windows 管理员权限检查
    └─ ws_server.py               # 早期独立 WebSocket 服务（当前未接入）
```

可选文件：`res/stealth.min.js`。若存在，会在每次页面加载完成后注入，用于降低自动化特征；仓库未附带时自动跳过。

---

## 实现要点

```text
QWebEngineView
├─ https://onlineweb.zhihuishu.com/onlinestuh5   智慧树在线学习页
└─ delion://zhs.ibin.cc?token=...&username=...    内置刷课页（自定义 scheme）
        ↕  WebSocket ws://127.0.0.1:9960/lesson
MainWindow（PySide6 + qasync）
├─ Access_to_public_courses / videos   课程、章节、视频与完成状态
├─ Report_progress                     进度上报
├─ Line_up                             批量队列
├─ slider_verify_async                 滑块验证
└─ auth / auth_http_server             应用授权登录
```

- **自定义协议**：`delion://` 在 `QApplication` 创建前注册，由 `UnifiedSchemeHandler` 返回内置 HTML；请求需携带 `token` 参数，否则返回 403。
- **本地通信**：内置页面连接 `ws://127.0.0.1:9960/lesson`，首帧发送 `handshake`（页面加载时间戳 + Token），服务端校验后才处理 `Select-课程`、`Report-进度`、`Batch-Report-进度`、`request_courses` 等指令。
- **进度上报**：先用 `prelearningNote` 获取学习记录 ID 与已学时长；若已学满则直接返回。否则以 10 秒为一个进度块计算总块数，每轮随机推进 5–20 秒，调用 `saveDatabaseIntervalTimeV2` 落库，间隔 1 秒，直到达到视频总时长。
- **请求加密**：课程与上报接口使用 AES-CBC/PKCS7 对 `secretStr` 加密；密钥与 IV 分别定义在 `modules/encryption.py`、`modules/Access_to_public_courses.py`、`modules/Report_progress.py`。
- **线程模型**：网络请求在线程池中执行，避免阻塞 Qt 主线程；跨线程日志通过 `progress_log` 信号回到 UI 线程。
- **登录态检测**：优先在页面内 `fetch` 用户信息接口（自动携带 HttpOnly Cookie），失败时降级检查 `document.cookie` 中的 `jt-cas`。

---

## 打包

打包依赖 cx_Freeze，未包含在 `requirements.txt` 中，需要单独安装：

```powershell
pip install cx_Freeze
python build.py build          # 生成可执行目录
python build.py bdist_msi      # 生成 Windows MSI 安装包
```

产物位于 `build/delion-ZHS-v1.0.0/`。打包配置要点：

- `base="Win32GUI"`：无控制台窗口；
- `uac_admin=True` + `app.manifest`：启动时请求管理员权限；
- 随包携带 `config.ini`、`assets`、`logs`、`app.manifest`；
- 桌面快捷方式名称 `delion-ZHS`。

> 不同 cx_Freeze 大版本对 `base` 取值与 `build_exe` 选项结构有差异；若打包报错，请先核对所用 cx_Freeze 版本与脚本写法是否匹配。

---

## 运行期资源

| 资源 | 位置 / 端口 | 说明 |
| --- | --- | --- |
| 内置页面 WebSocket | `127.0.0.1:9960` | 端口硬编码于 `modules/web.py` |
| 授权回调 HTTP 服务 | `127.0.0.1:19960` | 路径 `/Software/token` |
| 日志文件 | `logs/X-ZHS_YYYYMMDD.log` | 同时输出到控制台 |
| 授权令牌 | 开发环境 `zhslooen/looen.date`；打包环境 `C:\Program Files\zhslooen\looen.date` | 二进制格式，含魔数与长度头 |
| 用户配置 | 开发环境项目根目录；打包环境 exe 同目录 | `config.ini` |

---

## 常见问题

**滑块验证不自动执行？**
确认已安装 `opencv-python` 与 `numpy`。缺少任一依赖时程序仍可启动，但会跳过自动滑块，需要手动完成验证。页面结构变化也会导致选择器失效。

**提示「WebSocket 未连接」？**
内置页面与后端依赖 `9960` 端口。检查是否有其他实例占用该端口、本机安全软件是否拦截回环连接，然后刷新页面重试。

**授权登录一直失败？**
确认 `19960` 端口未被占用；授权回调需要本机浏览器能访问 `127.0.0.1`。打包版还需确保以管理员权限运行，否则可能无法写入 `C:\Program Files\zhslooen`。

**打包版启动提示权限不足？**
程序清单要求管理员权限。请在 UAC 弹窗中选择「是」，或右键以管理员身份运行。

**课程 / 视频列表为空？**
多为智慧树登录态失效或该课程暂无视频。重新登录后再点「刷课」；若仍为空，查看 `logs` 中的接口错误信息。

**刷课中途停止并跳到验证页？**
说明上报接口触发了平台安全验证。完成页面上的验证后无需手动返回，客户端检测到弹窗消失会自动回到刷课页。

---

## 已知限制

- 仅支持 Windows，未做跨平台适配；
- 不完整版不含刷题等完整功能；
- 账号密码以明文保存在 `config.ini`；
- 依赖智慧树接口、加密参数与页面 DOM 结构，平台改版后可能失效，需要同步调整 `modules/` 下对应实现；
- WebSocket 与回调端口为硬编码常量，暂不支持配置或多实例并行；
- `modules/ws_server.py` 为早期独立实现，当前链路未使用，保留仅作参考。

---

## 免责声明

本项目仅供个人学习与技术研究使用。使用本工具可能违反智慧树平台的服务条款及所在学校的学术规范，可能导致账号受限、学习记录无效等后果，风险由使用者自行承担。请遵守相关法律法规与平台规则，不要将本工具用于商业用途、代刷服务或其他侵权场景。

---

## 许可证

本仓库未附带 `LICENSE` 文件。如需复制、修改或分发代码，请先与作者确认授权方式。
