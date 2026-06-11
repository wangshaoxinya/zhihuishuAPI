"""
用户登录认证模块
处理令牌获取、存储、退出等功能
"""
import os
import sys
import time
import json
import base64
import struct
import hashlib
import hmac
import requests
from pathlib import Path
from typing import Optional, Dict, Any

# 配置常量
SERVER_DOMAIN = "zhs.shaoxin.top"
AUTH_API_PATH = "/ebpage/auth/looenv1"
REFRESH_API_PATH = "/ebpage/auth/loogenv1"
SIGNATURE_KEY = b"godan"
REFRESH_KEY = b"loogenv1"


def _get_data_dir() -> Path:
    """获取数据存储目录"""
    if getattr(sys, 'frozen', False):
        # 打包环境
        return Path(r"C:\Program Files\zhslooen")
    else:
        # 开发环境
        return Path(__file__).parent.parent / "zhslooen"


def _get_data_file_path() -> Path:
    """获取数据文件路径"""
    return _get_data_dir() / "looen.date"


def _generate_signature(message: str, timestamp: int, key: bytes = SIGNATURE_KEY) -> str:
    """生成签名

    Args:
        message: 消息内容
        timestamp: 时间戳（毫秒）
        key: 签名密钥

    Returns:
        签名（hex编码）
    """
    sign_str = f"{message}{timestamp}"
    hmac_obj = hmac.new(key, sign_str.encode('utf-8'), hashlib.sha256)
    return hmac_obj.hexdigest()


class AuthManager:
    """认证管理器"""

    def __init__(self):
        self._cached_token: Optional[str] = None
        self._cached_username: Optional[str] = None
        self._cached_expiry: Optional[int] = None

    def is_logged_in(self) -> bool:
        """检查是否已登录（本地存储有有效令牌）"""
        data = self._load_data()
        if not data:
            return False

        expiry = data.get("expiry", 0)
        current_time = int(time.time())
        return expiry > current_time

    def get_username(self) -> Optional[str]:
        """获取用户名"""
        data = self._load_data()
        return data.get("username") if data else None

    def get_token(self) -> Optional[str]:
        """获取有效令牌"""
        data = self._load_data()
        if not data:
            return None

        expiry = data.get("expiry", 0)
        current_time = int(time.time())
        if expiry > current_time:
            return data.get("token")
        return None

    def exchange_token(self, short_token: str) -> bool:
        """使用短令牌换取长令牌"""
        url = f"https://{SERVER_DOMAIN}{AUTH_API_PATH}"
        timestamp = int(time.time() * 1000)
        message = f"godan:{short_token}"
        signature = _generate_signature(message, timestamp)

        payload = {
            "godan": short_token,
            "timestamp": timestamp,
            "signature": signature
        }

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "delion-ZHS/1.0.0"
        }

        try:
            print(f"[Auth] ===== 发送请求 =====")
            print(f"[Auth] URL: {url}")
            print(f"[Auth] Headers: {headers}")
            print(f"[Auth] Payload: {payload}")

            response = requests.post(url, json=payload, headers=headers, timeout=15)
            
            print(f"[Auth] ===== 收到响应 =====")
            print(f"[Auth] Status Code: {response.status_code}")
            print(f"[Auth] Response Headers: {dict(response.headers)}")
            print(f"[Auth] Response Body: {response.text}")

            response.raise_for_status()
            result = response.json()

            # 方式1: 标准响应 { status: "success", data: { zhs_app_id, expires_at, username } }
            if result.get("status") == "success" and result.get("data"):
                data = result.get("data", {})
                zhs_app_id = data.get("zhs_app_id")
                expires_at = data.get("expires_at")
                username = data.get("username") or f"user_{zhs_app_id[:10]}"
                if zhs_app_id:
                    # expires_at 是毫秒时间戳
                    expiry = int(expires_at / 1000) if expires_at else int(time.time() + 86400 * 7)
                    self._save_data(zhs_app_id, username, expiry)
                    print(f"[Auth] 令牌交换成功: {zhs_app_id}, 用户: {username}")
                    return True

            # 方式2: 标准响应 { code: 0, token, username, expiry }
            if result.get("code") == 0:
                token = result.get("token")
                username = result.get("username")
                expiry = int(result.get("expiry", time.time() + 86400 * 7))
                self._save_data(token, username, expiry)
                return True

            # 方式3: 服务端返回 { zhs_app_id: "app_xxx" } (平铺格式)
            zhs_app_id = result.get("zhs_app_id")
            if zhs_app_id:
                username = f"user_{zhs_app_id[:10]}"
                expiry = int(time.time() + 86400 * 7)
                self._save_data(zhs_app_id, username, expiry)
                return True

            print(f"[Auth] 令牌交换失败: 未识别的响应格式")
            return False
        except requests.exceptions.HTTPError as e:
            print(f"[Auth] HTTP错误: {e}")
            print(f"[Auth] 响应内容: {e.response.text if e.response else 'N/A'}")
            return False
        except Exception as e:
            print(f"[Auth] 令牌交换失败: {e}")
            return False

    def refresh_token(self) -> bool:
        """刷新长令牌

        Returns:
            是否刷新成功
        """
        token = self.get_token()
        if not token:
            print("[Auth] 没有可用的令牌，无法刷新")
            return False

        url = f"https://{SERVER_DOMAIN}{REFRESH_API_PATH}"
        timestamp = int(time.time() * 1000)
        message = f"loogenv1:{token}"
        signature = _generate_signature(message, timestamp, REFRESH_KEY)

        payload = {
            "zhs_app_id": token,
            "timestamp": str(timestamp),
            "signature": signature
        }

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "delion-ZHS/1.0.0"
        }

        try:
            print(f"[Auth] ===== 刷新令牌请求 =====")
            print(f"[Auth] URL: {url}")
            print(f"[Auth] Headers: {headers}")
            print(f"[Auth] Payload: {payload}")

            response = requests.post(url, json=payload, headers=headers, timeout=15)

            print(f"[Auth] ===== 刷新令牌响应 =====")
            print(f"[Auth] Status Code: {response.status_code}")
            print(f"[Auth] Response Headers: {dict(response.headers)}")
            print(f"[Auth] Response Body: {response.text}")

            response.raise_for_status()
            result = response.json()

            if result.get("status") == "success" and result.get("data"):
                data = result.get("data", {})
                zhs_app_id = data.get("zhs_app_id")
                expires_at = data.get("expires_at")
                username = data.get("username") or self.get_username() or f"user_{zhs_app_id[:10]}"
                if zhs_app_id:
                    expiry = int(expires_at / 1000) if expires_at else int(time.time() + 86400 * 7)
                    self._save_data(zhs_app_id, username, expiry)
                    print(f"[Auth] 令牌刷新成功: {zhs_app_id}, 用户: {username}")
                    return True

            print(f"[Auth] 令牌刷新失败: 未识别的响应格式")
            return False
        except requests.exceptions.HTTPError as e:
            print(f"[Auth] 刷新令牌HTTP错误: {e}")
            print(f"[Auth] 响应内容: {e.response.text if e.response else 'N/A'}")
            return False
        except Exception as e:
            print(f"[Auth] 刷新令牌失败: {e}")
            return False

    def logout(self) -> bool:
        """退出登录（删除本地存储）"""
        try:
            data_file = _get_data_file_path()
            if data_file.exists():
                data_file.unlink()
            self._cached_token = None
            self._cached_username = None
            self._cached_expiry = None
            return True
        except Exception as e:
            print(f"[Auth] 退出登录失败: {e}")
            return False

    def _save_data(self, token: str, username: str, expiry: int) -> bool:
        """保存数据到文件（二进制）"""
        try:
            data_dir = _get_data_dir()
            data_dir.mkdir(parents=True, exist_ok=True)

            data = {
                "token": token,
                "username": username,
                "expiry": expiry
            }
            json_str = json.dumps(data, ensure_ascii=False)

            with open(_get_data_file_path(), "wb") as f:
                # 写入魔数 + 版本
                f.write(b"ZHS\x01")
                # 写入数据长度
                data_bytes = json_str.encode("utf-8")
                f.write(struct.pack("<I", len(data_bytes)))
                # 写入数据
                f.write(data_bytes)

            self._cached_token = token
            self._cached_username = username
            self._cached_expiry = expiry
            return True
        except Exception as e:
            print(f"[Auth] 保存数据失败: {e}")
            return False

    def _load_data(self) -> Optional[Dict[str, Any]]:
        """从文件加载数据"""
        try:
            data_file = _get_data_file_path()
            if not data_file.exists():
                return None

            with open(data_file, "rb") as f:
                # 验证魔数
                magic = f.read(4)
                if magic != b"ZHS\x01":
                    return None

                # 读取数据长度
                size_data = f.read(4)
                if len(size_data) != 4:
                    return None
                data_size = struct.unpack("<I", size_data)[0]

                # 读取数据
                json_bytes = f.read(data_size)
                if len(json_bytes) != data_size:
                    return None

                return json.loads(json_bytes.decode("utf-8"))
        except Exception as e:
            print(f"[Auth] 加载数据失败: {e}")
            return None


# 全局实例
_auth_manager: Optional[AuthManager] = None


def get_auth_manager() -> AuthManager:
    """获取认证管理器单例"""
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = AuthManager()
    return _auth_manager
