"""
本地HTTP服务模块
监听127.0.0.1:19960，接收登录网页传来的短令牌
"""
import asyncio
import json
from typing import Optional, Callable, Any
from aiohttp import web

from modules.auth import get_auth_manager

# 配置常量
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 19960
TOKEN_PATH = "/Software/token"

# 全局变量
_server: Optional[web.TCPSite] = None
_runner: Optional[web.AppRunner] = None
_app: Optional[web.Application] = None
_on_login_success: Optional[Callable[[str], Any]] = None


async def _handle_token(request):
    """处理令牌接收请求"""
    # 添加CORS头
    cors_headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }

    if request.method == "OPTIONS":
        return web.Response(status=200, headers=cors_headers)

    if request.method != "POST":
        return web.Response(status=405, headers=cors_headers, text="Method Not Allowed")

    try:
        data = await request.json()
        print(f"[AuthServer] 收到请求数据: {data}")
        # 支持多种参数名: code, Code, token
        code = data.get("code") or data.get("Code") or data.get("token")

        if not code:
            return web.json_response({"code": -1, "message": "Missing code/token"}, status=400, headers=cors_headers)

        # 交换令牌
        auth_manager = get_auth_manager()
        success = auth_manager.exchange_token(code)

        if success:
            username = auth_manager.get_username() or "User"

            # 回调通知登录成功
            if _on_login_success:
                try:
                    if asyncio.iscoroutinefunction(_on_login_success):
                        await _on_login_success(username)
                    else:
                        _on_login_success(username)
                except Exception as e:
                    print(f"[AuthServer] 登录回调失败: {e}")

            return web.json_response({"code": 0, "message": "Success", "username": username}, headers=cors_headers)
        else:
            return web.json_response({"code": -2, "message": "Token exchange failed"}, status=400, headers=cors_headers)
    except json.JSONDecodeError as e:
        print(f"[AuthServer] JSON解析失败: {e}")
        return web.json_response({"code": -1, "message": "Invalid JSON"}, status=400, headers=cors_headers)
    except Exception as e:
        print(f"[AuthServer] 请求处理失败: {e}")
        return web.json_response({"code": -1, "message": str(e)}, status=500, headers=cors_headers)


def _create_app():
    """创建aiohttp应用"""
    app = web.Application()
    app.router.add_route("*", TOKEN_PATH, _handle_token)
    return app


async def start_auth_server(callback: Optional[Callable[[str], Any]] = None) -> bool:
    """
    启动本地HTTP服务

    Args:
        callback: 登录成功回调函数，接收用户名

    Returns:
        是否成功启动
    """
    global _server, _runner, _app, _on_login_success

    if _server is not None:
        print("[AuthServer] 服务已在运行")
        return False

    try:
        _on_login_success = callback
        _app = _create_app()

        _runner = web.AppRunner(_app)
        await _runner.setup()
        site = web.TCPSite(_runner, SERVER_HOST, SERVER_PORT)
        await site.start()

        _server = site
        print(f"[AuthServer] 服务已启动: http://{SERVER_HOST}:{SERVER_PORT}")
        return True
    except Exception as e:
        print(f"[AuthServer] 启动失败: {e}")
        return False


async def stop_auth_server():
    """停止HTTP服务"""
    global _server, _runner, _app

    if _runner is not None:
        try:
            await _runner.cleanup()
        except Exception as e:
            print(f"[AuthServer] 停止服务失败: {e}")

    _server = None
    _runner = None
    _app = None
    print("[AuthServer] 服务已停止")


def is_server_running() -> bool:
    """检查服务是否正在运行"""
    return _runner is not None
