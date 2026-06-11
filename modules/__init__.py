"""
__init__.py - 通用模块包初始化文件
提供统一的模块导入接口
"""
from .logger import Logger, get_logger
from .config import ConfigManager, AppConfig, get_config
from .ini_config import IniConfig, get_ini_config
from .slider_verify_async import (
    SliderVerifier,
    CourseInfo,
    CourseListResult,
    download_image_async,
    process_background_image,
    process_block_image,
    calculate_slider_position,
    gen_movelist,
)
from .cookie_checker import CookieChecker
from . import web as web_module
from .auth import AuthManager, get_auth_manager
from .auth_http_server import (
    start_auth_server,
    stop_auth_server,
    is_server_running
)
from .uac_manager import (
    is_admin,
    run_as_admin,
    ensure_admin
)

# 保持向后兼容性
download_image = download_image_async

__all__ = [
    'Logger',
    'get_logger',
    'ConfigManager',
    'AppConfig',
    'get_config',
    'IniConfig',
    'get_ini_config',
    'SliderVerifier',
    'CourseInfo',
    'CourseListResult',
    'CookieChecker',
    'download_image',
    'download_image_async',
    'process_background_image',
    'process_block_image',
    'calculate_slider_position',
    'gen_movelist',
    'web_module',
    'AuthManager',
    'get_auth_manager',
    'start_auth_server',
    'stop_auth_server',
    'is_server_running',
    'is_admin',
    'run_as_admin',
    'ensure_admin'
]
