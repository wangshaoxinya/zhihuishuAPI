"""
通用配置管理模块 - 可独立复用到其他项目
默认配置直接写在代码中
"""
import os
from pathlib import Path
from typing import Any, Optional, Dict
from dataclasses import dataclass, field


@dataclass
class AppConfig:
    """应用程序配置数据类"""
    app_name: str = "X-ZHS"
    app_version: str = "1.0.0"
    author: str = "Your Name"
    debug: bool = False

    url: str = "https://onlineweb.zhihuishu.com/onlinestuh5"
    auto_start: bool = False

    window_width: int = 1400
    window_height: int = 700
    window_title: str = "delion智慧树"

    log_level: str = "INFO"
    log_dir: Optional[str] = None

    custom_settings: Dict[str, Any] = field(default_factory=dict)


class ConfigManager:
    """配置管理器，使用代码中的默认配置"""

    _default_config = AppConfig()

    def __init__(self, config_path: Optional[str] = None):
        """初始化配置管理器

        Args:
            config_path: 保留参数，但不再使用
        """
        self._config: AppConfig = self._default_config

    def load(self) -> AppConfig:
        """加载配置（直接返回默认配置）"""
        return self._config

    def save(self, config: Optional[AppConfig] = None):
        """保存配置（暂不支持）"""
        pass

    def get(self) -> AppConfig:
        """获取当前配置"""
        return self._config

    def update(self, **kwargs):
        """更新配置项（运行时生效）"""
        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)


def get_config(config_path: Optional[str] = None) -> ConfigManager:
    """获取配置管理器的便捷函数

    Args:
        config_path: 保留参数，但不再使用

    Returns:
        ConfigManager 实例
    """
    return ConfigManager(config_path)
