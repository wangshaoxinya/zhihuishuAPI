# zhihuishuapi - 智慧树学习辅助工具

基于 PySide6 + QWebEngine 构建的桌面应用，用于智慧树在线学习平台的自动化辅助。

> 开源版本只提供刷课功能，如需完整功能请前往 [zhs.shaoxin.top](https://zhs.shaoxin.top) 获取。

## 功能特性

- 自动登录（账号密码 / 扫码登录）
- 滑块验证码自动识别
- 课程列表获取与展示
- 视频学习进度自动上报
- 批量刷课（队列模式）
- 实时进度显示
- WebSocket 实时通信

## 环境要求

- Python 3.10+
- Windows 10/11

## 安装依赖

```bash
pip install -r requirements.txt
```

主要依赖：
- PySide6 - Qt框架
- PySide6-WebEngine - 浏览器引擎
- qasync - 异步Qt支持
- opencv-python - 滑块验证码识别
- requests - HTTP请求
- aiohttp - 本地服务器
- websockets - WebSocket通信
- pycryptodome - 加密模块

## 运行方法

```bash
python main.py
```

## 使用说明

1. 启动程序后，点击右上角「登录」按钮
2. 在弹出的网页中完成登录（支持账号密码或扫码）
3. 登录成功后，点击「刷课」按钮
4. 选择要学习的课程
5. 勾选需要刷的视频，点击「开始刷课」
6. 等待队列处理完成

## 注意事项

- 首次运行需要安装所有依赖
- 建议使用管理员权限运行（部分功能需要）
- 刷课过程中请勿关闭程序
- 如遇到安全验证，请手动完成验证后程序会自动继续

## 免责声明

本项目仅供学习交流使用，请勿用于商业用途。使用本工具产生的一切后果由使用者自行承担。

## 项目标签

#x-zhs  #zhihuishuAPI  #zhihuishuapi
