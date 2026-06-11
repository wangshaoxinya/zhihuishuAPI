"""
Cookie 检查模块

用于检查浏览器中是否存在登录相关的 cookie，以判断用户是否已登录。
通过浏览器内 fetch 请求 API 验证登录状态（fetch 自动携带 HttpOnly Cookie）。
支持 cookie 持久化存储，重启后为空，登录成功后保存。
"""
import asyncio
import json
from typing import Optional, List


# 模块级缓存（每次重启为空，登录成功后才写入）
_saved_cookie: str = ""


def save_cookie_one(cookie_str: str):
    """保存 cookie 字符串到内存缓存

    Args:
        cookie_str: 登录后的完整 cookie 字符串
    """
    global _saved_cookie
    _saved_cookie = cookie_str


def get_saved_cookie() -> str:
    """获取已保存的 cookie 字符串

    Returns:
        保存的 cookie 字符串，未保存时返回空字符串
    """
    return _saved_cookie


class CookieChecker:
    """Cookie 检查器"""

    REQUIRED_COOKIES = [
        'CASTGC',      # CAS 登录 ticket
        'jt-cas',      # JWT token
        'SESSION',     # Session ID
        'CASLOGC'      # CAS 登录信息
    ]

    def __init__(self, browser_engine=None):
        """初始化检查器"""
        self.browser_engine = browser_engine

    def set_browser_engine(self, browser_engine):
        """设置浏览器引擎"""
        self.browser_engine = browser_engine

    async def check_login_cookies(self) -> bool:
        """通过 fetch 请求 API 验证登录状态（自动携带 HttpOnly Cookie）"""
        if not self.browser_engine:
            return False

        # 方法1：通过 fetch 请求用户信息 API 验证登录
        is_logged_in = await self._check_login_by_fetch()
        if is_logged_in is not None:
            return is_logged_in

        # 方法2：降级为 document.cookie 检查（不支持 HttpOnly）
        return await self._check_login_by_js_cookies()

    async def _check_login_by_fetch(self) -> Optional[bool]:
        """通过 fetch 请求智慧树 API 验证是否已登录"""
        script = """
        (async function() {
            try {
                var response = await fetch(
                    'https://studyservice-api.zhihuishu.com/gateway/f/v1/login/getLoginUserInfo?dateFormate=' + Date.now(),
                    {
                        method: 'GET',
                        credentials: 'include'
                    }
                );
                if (response.ok) {
                    var data = await response.json();
                    if (data && data.data && data.data.realName) {
                        return JSON.stringify({loggedIn: true, name: data.data.realName});
                    }
                }
                return JSON.stringify({loggedIn: false});
            } catch(e) {
                return JSON.stringify({error: e.message || 'fetch failed'});
            }
        })();
        """

        result = await self._run_js(script)
        if not result:
            return None

        try:
            data = json.loads(result)
            if 'error' in data:
                return None
            return data.get('loggedIn', False)
        except (json.JSONDecodeError, TypeError):
            return None

    async def _check_login_by_js_cookies(self) -> bool:
        """降级方案：通过 document.cookie 检查（不支持 HttpOnly）"""
        script = """
        (function() {
            return document.cookie;
        })();
        """

        cookie_str = await self._run_js(script)
        if not cookie_str:
            return False

        cookies = self.parse_cookies_from_string(cookie_str)
        # 只检查非 HttpOnly 的 cookie
        non_httponly = ['jt-cas']
        return all(name in cookies for name in non_httponly)

    async def _run_js(self, script: str, timeout: float = 8.0):
        """执行 JavaScript 并等待结果"""
        future = asyncio.Future()

        def callback(result):
            if not future.done():
                future.set_result(result)

        self.browser_engine.run_javascript(script, callback)

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            return None

    def parse_cookies_from_string(self, cookie_string: str) -> dict:
        """从字符串解析 cookies"""
        cookies = {}
        for part in cookie_string.split(';'):
            part = part.strip()
            if '=' in part:
                name, value = part.split('=', 1)
                cookies[name.strip()] = value.strip()
        return cookies

    def check_cookies_from_string(self, cookie_string: str) -> bool:
        """检查 cookie 字符串是否包含登录信息"""
        cookies = self.parse_cookies_from_string(cookie_string)
        return all(name in cookies for name in self.REQUIRED_COOKIES)
