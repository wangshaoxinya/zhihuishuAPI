"""
应用程序入口文件
使用 PySide6 + QWebEngine 构建桌面应用
集成 qasync 支持异步操作
"""
import sys
import os
import asyncio
from pathlib import Path
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt
import qasync

sys.path.insert(0, str(Path(__file__).parent))

from components import MainWindow
from modules import get_config, get_logger, AppConfig
from modules import web as app_web
from modules import ensure_admin, stop_auth_server


def setup_qt_environment():
    """配置 Qt 环境"""
    os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")

    os.environ.setdefault(
        "QT_QPA_PLATFORM_PLUGIN_PATH",
        os.path.dirname(os.path.abspath(__file__))
    )


def get_application_icon_path() -> str:
    """获取应用图标路径"""
    if getattr(sys, 'frozen', False):
        # 打包环境
        base_dir = Path(sys.executable).parent
        icon_path = base_dir / "assets" / "delion.ico"
    else:
        # 开发环境
        base_dir = Path(__file__).parent
        icon_path = base_dir / "assets" / "delion.ico"
    return str(icon_path) if icon_path.exists() else ""


async def main_async():
    """异步主函数"""
    setup_qt_environment()

    # 注册自定义 URL Scheme（必须在 QApplication 创建前调用）
    app_web.register_custom_scheme()

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    app.setApplicationName("X-ZHS")
    app.setOrganizationName("X-ZHS")
    
    # 设置应用图标（确保任务栏显示正确的图标）
    icon_path = get_application_icon_path()
    if icon_path:
        from PySide6.QtGui import QIcon
        app.setWindowIcon(QIcon(icon_path))

    try:
        config_manager = get_config()
        config = config_manager.load()

        if config.debug:
            QMessageBox.information(
                None,
                "调试模式",
                f"应用名称: {config.app_name}\n"
                f"版本: {config.app_version}\n"
                f"作者: {config.author}\n"
                f"窗口大小: {config.window_width}x{config.window_height}"
            )

        window = MainWindow(config)
        window.show()

        # 使用 qasync 的事件循环
        future = asyncio.Future()
        
        def on_about_to_quit():
            # 关闭所有服务
            asyncio.create_task(app_web.stop_ws_server())
            asyncio.create_task(stop_auth_server())
            future.set_result(None)
        
        app.aboutToQuit.connect(on_about_to_quit)
        await future

    except Exception as e:
        logger = get_logger("Error")
        logger.error(f"应用程序启动失败: {e}")

        QMessageBox.critical(
            None,
            "错误",
            f"应用程序启动失败:\n\n{str(e)}\n\n"
            f"请检查以下依赖是否已安装:\n"
            f"  - PySide6\n"
            f"  - PySide6-WebEngine\n"
            f"  - requests\n"
            f"  - opencv-python\n"
            f"  - numpy\n"
            f"  - qasync\n"
            f"  - aiohttp"
        )

        sys.exit(1)


def main():
    """主函数 - qasync 启动器"""
    # 检查并确保管理员权限（仅打包环境）
    ensure_admin()
    
    # 设置 Windows AppUserModelID（必须在 QApplication 创建之前）
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("X-ZHS.delion.zhs.1.0.0")
    
    qasync.run(main_async())


if __name__ == "__main__":
    main()
