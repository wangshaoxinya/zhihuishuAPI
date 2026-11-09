"""
INI 配置文件管理模块 - 用于存储用户配置
支持倍速、账户、密码等敏感信息的读写
"""
import os
import sys
import configparser
from pathlib import Path
from typing import Optional


def _get_base_dir() -> Path:
    """获取应用根目录（兼容打包和开发环境）"""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent.parent


class IniConfig:
    """INI 配置文件管理类"""

    def __init__(self, config_path: Optional[str] = None):
        """初始化 INI 配置管理器

        Args:
            config_path: 配置文件路径，默认使用 config.ini
        """
        if config_path is None:
            config_path = _get_base_dir() / "config.ini"

        self.config_path = Path(config_path)
        self.config = configparser.ConfigParser()
        self._load()

    def _load(self):
        """从文件加载配置"""
        if self.config_path.exists():
            self.config.read(self.config_path, encoding='utf-8')
        else:
            self._create_default()

    def _create_default(self):
        """创建默认配置"""
        if not self.config.has_section('user'):
            self.config.add_section('user')

        self.config.set('user', 'account', '')
        self.config.set('user', 'password', '')
        self.config.set('user', 'auto_login_enabled', 'false')
        self.save()

    def save(self):
        """保存配置到文件"""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, 'w', encoding='utf-8') as f:
            self.config.write(f)

    def get_account(self) -> str:
        """获取账户"""
        return self.config.get('user', 'account', fallback='')

    def set_account(self, account: str):
        """设置账户"""
        self.config.set('user', 'account', account)
        self.save()

    def get_password(self) -> str:
        """获取密码"""
        return self.config.get('user', 'password', fallback='')

    def set_password(self, password: str):
        """设置密码"""
        self.config.set('user', 'password', password)
        self.save()

    def get_all(self) -> dict:
        """获取所有配置"""
        return {
            'account': self.get_account(),
            'password': self.get_password(),
            'auto_login_enabled': self.get_auto_login_enabled()
        }

    def get_auto_login_enabled(self) -> bool:
        """获取自动登录开关状态"""
        return self.config.getboolean('user', 'auto_login_enabled', fallback=False)

    def set_auto_login_enabled(self, enabled: bool):
        """设置自动登录开关状态"""
        self.config.set('user', 'auto_login_enabled', 'true' if enabled else 'false')
        self.save()


def get_ini_config(config_path: Optional[str] = None) -> IniConfig:
    """获取 INI 配置管理器的便捷函数

    Args:
        config_path: 配置文件路径

    Returns:
        IniConfig 实例
    """
    return IniConfig(config_path)
