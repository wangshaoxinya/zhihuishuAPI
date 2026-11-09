"""
通用日志模块 - 可独立复用到其他项目
提供统一的日志记录功能，支持控制台和文件输出
"""
import os
import sys
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional


class Logger:
    """通用日志记录器类"""

    _instances = {}

    def __new__(cls, name: str = "App", log_dir: Optional[str] = None):
        """单例模式，确保同一个名称只创建一个日志实例"""
        if name not in cls._instances:
            instance = super().__new__(cls)
            cls._instances[name] = instance
        return cls._instances[name]

    def __init__(self, name: str = "App", log_dir: Optional[str] = None):
        """初始化日志记录器

        Args:
            name: 日志记录器名称
            log_dir: 日志文件保存目录，默认保存在项目根目录的 logs 文件夹
        """
        if hasattr(self, '_initialized') and self._initialized:
            return

        self.name = name
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers.clear()

        if log_dir is None:
            log_dir = Path(__file__).parent.parent / "logs"

        os.makedirs(log_dir, exist_ok=True)
        log_file = Path(log_dir) / f"{name}_{datetime.now().strftime('%Y%m%d')}.log"

        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)

        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

        self._initialized = True

    def debug(self, message: str):
        """记录调试信息"""
        self.logger.debug(message)

    def info(self, message: str):
        """记录一般信息"""
        self.logger.info(message)

    def warn(self, message: str):
        """记录警告信息"""
        self.logger.warning(message)
    
    def warning(self, message: str):
        """记录警告信息（别名方法）"""
        self.logger.warning(message)

    def error(self, message: str):
        """记录错误信息"""
        self.logger.error(message)

    def critical(self, message: str):
        """记录严重错误信息"""
        self.logger.critical(message)


def get_logger(name: str = "App", log_dir: Optional[str] = None) -> Logger:
    """获取日志记录器实例的便捷函数

    Args:
        name: 日志记录器名称
        log_dir: 日志文件保存目录

    Returns:
        Logger 实例
    """
    return Logger(name, log_dir)
