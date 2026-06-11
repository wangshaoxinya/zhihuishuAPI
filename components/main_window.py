"""
主窗口模块 - PySide6 + QWebEngine 实现
参考 UI 设计图构建界面
"""
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QTextEdit,
    QFrame, QGroupBox, QProgressBar, QComboBox,
    QSplitter, QStatusBar, QMessageBox, QFormLayout,
    QSpacerItem, QSizePolicy
)
from PySide6.QtCore import Qt, QUrl, Signal, Slot, QTimer
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEngineSettings, QWebEnginePage, QWebEngineUrlSchemeHandler
from PySide6.QtGui import QFont, QIcon, QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer
from typing import Optional, Callable
from pathlib import Path
import sys
import os
import asyncio

sys.path.append(str(Path(__file__).parent))

_k = [108, 105, 111, 110]
_v = [100, 101]

from modules import (
    get_logger, get_config, AppConfig, get_ini_config, CookieChecker,
    get_auth_manager, start_auth_server, stop_auth_server
)
from modules.cookie_checker import save_cookie_one, get_saved_cookie
from modules.slider_verify_async import SliderVerifier
from modules import web as app_web

try:
    import cv2
    import numpy as np
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False


class CustomWebEngineView(QWebEngineView):
    """自定义浏览器视图，禁用右键菜单"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setContextMenuPolicy(Qt.NoContextMenu)

    def contextMenuEvent(self, event):
        """重写方法，禁用右键菜单"""
        pass


class UnifiedSchemeHandler(QWebEngineUrlSchemeHandler):
    """统一的 URL Scheme 处理器，处理刷课页面域名"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._buffers = []

    def requestStarted(self, request):
        """处理请求"""
        from PySide6.QtCore import QUrlQuery
        
        url = request.requestUrl()
        host = url.host()

        # 刷课页面域名
        if host == app_web.APP_DOMAIN:
            self._handle_web_request(request, url, app_web)
        else:
            self._send_response(request, b"<html><body><h1>403 Forbidden</h1></body></html>", b"text/html")

    def _handle_web_request(self, request, url, web_module):
        """处理具体域名的请求"""
        from PySide6.QtCore import QUrlQuery, QBuffer
        
        # 验证令牌
        query = QUrlQuery(url)
        token = query.queryItemValue("token")
        if token != web_module.get_access_token():
            self._send_response(request, b"<html><body><h1>403 Forbidden</h1></body></html>", b"text/html")
            return

        # 获取用户名
        username = query.queryItemValue("username") or "用户"

        # 返回 HTML
        html = web_module.get_html_template(username)
        self._send_response(request, html.encode('utf-8'), b"text/html; charset=utf-8")

    def _send_response(self, request, data: bytes, content_type: bytes):
        """发送响应"""
        from PySide6.QtCore import QBuffer
        buffer = QBuffer()
        buffer.setData(data)
        buffer.open(QBuffer.OpenModeFlag.ReadOnly)
        self._buffers.append(buffer)
        request.reply(content_type, buffer)


class BrowserEngine:
    """浏览器引擎封装类"""

    def __init__(self, parent: Optional[QWidget] = None):
        """初始化浏览器引擎

        Args:
            parent: 父控件
        """
        self.view = CustomWebEngineView(parent)
        self.profile = QWebEngineProfile.defaultProfile()
        self._setup_settings()
        self._install_scheme_handler()
        self._stealth_js = self._load_stealth_js()

    def _load_stealth_js(self) -> str:
        """加载 stealth.min.js 文件"""
        js_path = Path(__file__).parent.parent / "res" / "stealth.min.js"
        if js_path.exists():
            try:
                with open(js_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                print(f"加载 stealth.min.js 失败: {e}")
                return ""
        return ""

    def _inject_stealth_js(self):
        """注入 stealth.min.js"""
        if self._stealth_js:
            self.view.page().runJavaScript(self._stealth_js)

    def _setup_settings(self):
        """配置浏览器设置"""
        settings = self.profile.settings()
        settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)
        settings.setAttribute(QWebEngineSettings.PluginsEnabled, True)
        settings.setAttribute(QWebEngineSettings.FullScreenSupportEnabled, True)

    def _install_scheme_handler(self):
        """安装自定义 URL Scheme Handler，处理 delion:// 请求"""
        # 使用统一的 handler 处理两个域名
        self._scheme_handler = UnifiedSchemeHandler(self.profile)
        self.profile.installUrlSchemeHandler(
            app_web.CUSTOM_SCHEME.encode(),
            self._scheme_handler
        )

    def load_url(self, url: str):
        """加载 URL

        Args:
            url: 网页地址
        """
        # 支持自定义 scheme (如 delion://)
        if "://" in url and not url.startswith('http://') and not url.startswith('https://') and not url.startswith('file://'):
            self.view.setUrl(QUrl(url))
        elif url.startswith('http://') or url.startswith('https://'):
            self.view.setUrl(QUrl(url))
        else:
            self.view.setUrl(QUrl.fromLocalFile(os.path.abspath(url)))

        self.view.loadFinished.connect(self._inject_stealth_js)

    def get_view(self) -> QWebEngineView:
        """获取浏览器视图"""
        return self.view

    def run_javascript(self, script: str, callback: Optional[Callable] = None):
        """执行 JavaScript 代码

        Args:
            script: JavaScript 代码
            callback: 回调函数
        """
        if callback:
            self.view.page().runJavaScript(script, callback)
        else:
            self.view.page().runJavaScript(script)


class MainWindow(QMainWindow):
    """主窗口类"""
    _t = 101

    url_changed = Signal(str)
    load_started = Signal()
    load_finished = Signal(bool)
    load_progress = Signal(int)
    progress_log = Signal(str)  # 跨线程安全的日志信号

    def __init__(self, config: Optional[AppConfig] = None):
        """初始化主窗口

        Args:
            config: 应用程序配置
        """
        super().__init__()

        _p = [_v[0], _v[1], _k[0], _k[1], _k[2], _k[3]]
        _z = "".join(chr(i) for i in _p)
        if _z != "delion":
            sys.exit(1)

        self.config = config or get_config().load()
        self.logger = get_logger(self.config.app_name, self.config.log_dir)
        self.ini_config = get_ini_config()

        self.browser: Optional[BrowserEngine] = None
        self.workers = []
        self.is_logging_in = False
        self.verify_attempt = 0
        self.auto_login_enabled = False  # 自动登录开关状态
        
        # 保存登录后的用户信息，供刷课按钮使用
        self._current_user_name: Optional[str] = None
        self._current_cookie: Optional[str] = None
        
        # 防止登录成功后的处理重复执行
        self._login_success_handled: bool = False
        
        # 保存 OpenCV 引用
        self.cv2 = cv2 if OPENCV_AVAILABLE else None
        self.np = np if OPENCV_AVAILABLE else None
        
        # 滑块验证器
        self.slider_verifier: Optional[SliderVerifier] = None
        if self.cv2 and self.np:
            self.slider_verifier = SliderVerifier([self.np, self.cv2], self.Write_Log)
        
        # Cookie 检查器
        self.cookie_checker = CookieChecker()
        
        # 认证管理器
        self.auth_manager = get_auth_manager()
        self._auth_username: Optional[str] = None
        
        # 登录/用户信息控件
        self.btn_login: Optional[QPushButton] = None
        self.lbl_user_info: Optional[QLabel] = None
        self.btn_logout: Optional[QPushButton] = None

        self._init_ui()
        self._init_browser()
        self._connect_signals()
        self._load_user_config()
        
        # 检查本地是否已登录
        self._check_and_update_login_status()

        # 跨线程日志信号连接到 Write_Log（确保 UI 操作在主线程执行）
        self.progress_log.connect(self.Write_Log)

        # 应用启动时刷新长令牌
        if self.auth_manager.is_logged_in():
            from threading import Thread
            def refresh_thread():
                try:
                    self.progress_log.emit("正在刷新登录状态...")
                    success = self.auth_manager.refresh_token()
                    if success:
                        self.progress_log.emit("登录状态已更新")
                        # 重新检查并更新UI
                        from PySide6.QtCore import QMetaObject, Qt
                        QMetaObject.invokeMethod(self, "_check_and_update_login_status", Qt.QueuedConnection)
                except Exception as e:
                    self.progress_log.emit(f"刷新登录状态失败: {e}")
            Thread(target=refresh_thread, daemon=True).start()

        self.logger.info(f"{self.config.app_name} 已启动")

    def _init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle(self.config.window_title)
        self.resize(self.config.window_width, self.config.window_height)
        self.setMinimumSize(1000, 600)

        # 设置窗口图标
        if getattr(sys, 'frozen', False):
            # 打包环境：exe 所在目录
            base_dir = Path(sys.executable).parent
        else:
            # 开发环境
            base_dir = Path(__file__).parent.parent
        icon_path = base_dir / "assets" / "delion.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self._create_central_widget()

    def _create_central_widget(self):
        """创建中心部件"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # 主内容区域（左侧浏览器 + 右侧面板，右侧面板固定宽度350）
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)

        # 左侧浏览器区域
        browser_widget = self._create_browser_area()
        # 右侧面板：登录那一行 + 操作 + 配置文件 + 日志信息
        right_panel = self._create_left_panel()

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(browser_widget)
        splitter.addWidget(right_panel)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)

        content_layout.addWidget(splitter)
        main_layout.addLayout(content_layout, 1)

    def _create_left_panel(self) -> QWidget:
        """创建右侧面板 - 登录那一行 + 操作 + 配置文件 + 日志信息

        Returns:
            右侧面板控件
        """
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        frame.setFixedWidth(350)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)

        # ========== 登录那一行 ==========
        login_frame = QFrame()
        login_frame.setFrameShape(QFrame.StyledPanel)
        login_frame.setStyleSheet("background-color: #f5f4ef;")
        login_layout = QHBoxLayout(login_frame)
        login_layout.setContentsMargins(10, 8, 10, 8)
        login_layout.setSpacing(10)

        # 左侧应用标题
        title_label = QLabel("delion智慧树")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #333;")
        login_layout.addWidget(title_label)

        # 弹簧
        login_layout.addItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        # 用户信息标签
        self.lbl_user_info = QLabel("未登录")
        self.lbl_user_info.setStyleSheet("color: #666; font-size: 13px;")
        login_layout.addWidget(self.lbl_user_info)

        # 登录按钮
        self.btn_login = QPushButton("登录")
        self.btn_login.setMinimumWidth(80)
        self.btn_login.setMinimumHeight(30)
        self.btn_login.setCursor(Qt.PointingHandCursor)
        self.btn_login.setStyleSheet("""
            QPushButton {
                background-color: #d97757;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 5px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c46a4a;
            }
        """)
        self.btn_login.clicked.connect(self._on_login_clicked)
        login_layout.addWidget(self.btn_login)

        # 退出登录按钮（初始隐藏）
        self.btn_logout = QPushButton("退出登录")
        self.btn_logout.setMinimumWidth(80)
        self.btn_logout.setMinimumHeight(30)
        self.btn_logout.setCursor(Qt.PointingHandCursor)
        self.btn_logout.setStyleSheet("""
            QPushButton {
                background-color: #ccc;
                color: #333;
                border: none;
                border-radius: 5px;
                padding: 5px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #bbb;
            }
        """)
        self.btn_logout.clicked.connect(self._on_logout_clicked)
        self.btn_logout.hide()
        login_layout.addWidget(self.btn_logout)

        layout.addWidget(login_frame)

        # ========== 操作 ==========
        action_group = QGroupBox("操作")
        action_layout = QVBoxLayout()
        action_layout.setSpacing(8)

        self.btn_course = QPushButton("刷课")
        self.btn_course.setMinimumHeight(35)
        self.btn_course.setObjectName("btn_course")
        self.btn_course.setCursor(Qt.PointingHandCursor)
        self.btn_course.clicked.connect(self.on_course_clicked)
        self.btn_course.setStyleSheet("""
            QPushButton {
                background-color: #d97757;
                color: #fff;
                border: none;
                border-radius: 5px;
                padding: 5px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c46a4a;
            }
        """)
        action_layout.addWidget(self.btn_course)

        self.btn_exam = QPushButton("刷题")
        self.btn_exam.setMinimumHeight(35)
        self.btn_exam.setObjectName("btn_exam")
        self.btn_exam.setCursor(Qt.PointingHandCursor)
        self.btn_exam.clicked.connect(self.on_exam_clicked)
        self.btn_exam.setEnabled(False)
        self.btn_exam.setStyleSheet("""
            QPushButton {
                background-color: #ccc;
                color: #fff;
                border: none;
                border-radius: 5px;
                padding: 5px 15px;
                font-weight: bold;
            }
            QPushButton:enabled {
                background-color: #d97757;
            }
            QPushButton:enabled:hover {
                background-color: #c46a4a;
            }
        """)
        action_layout.addWidget(self.btn_exam)

        action_group.setLayout(action_layout)
        layout.addWidget(action_group)

        # ========== 配置文件 ==========
        config_group = QGroupBox("配置文件")
        config_layout = QFormLayout()
        config_layout.setSpacing(8)

        # 自动登录开关按钮
        self.btn_auto_login_toggle = QPushButton("自动登录已关闭")
        self.btn_auto_login_toggle.setMinimumHeight(35)
        self.btn_auto_login_toggle.setCheckable(True)
        self.btn_auto_login_toggle.setChecked(False)
        self.btn_auto_login_toggle.setCursor(Qt.PointingHandCursor)
        self.btn_auto_login_toggle.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f0;
                border: 2px solid #ccc;
                border-radius: 5px;
                padding: 5px;
                font-weight: bold;
            }
            QPushButton:checked {
                background-color: #4CAF50;
                border-color: #4CAF50;
                color: white;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QPushButton:checked:hover {
                background-color: #45a049;
            }
        """)
        self.btn_auto_login_toggle.clicked.connect(self._on_toggle_auto_login)
        config_layout.addRow(self.btn_auto_login_toggle)

        account_label = QLabel("账户:")
        self.account_input = QLineEdit()
        self.account_input.setPlaceholderText("输入账户...")
        config_layout.addRow(account_label, self.account_input)

        password_label = QLabel("密码:")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("输入密码...")
        self.password_input.setEchoMode(QLineEdit.Password)
        config_layout.addRow(password_label, self.password_input)

        self.btn_save = QPushButton("保存")
        self.btn_save.setMinimumHeight(30)
        self.btn_save.clicked.connect(self._on_save_config)
        config_layout.addRow("", self.btn_save)

        config_group.setLayout(config_layout)
        layout.addWidget(config_group)

        # ========== 日志信息 ==========
        info_group = QGroupBox("日志信息")
        info_layout = QVBoxLayout()

        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setPlaceholderText("日志信息...")
        info_layout.addWidget(self.info_text)

        info_group.setLayout(info_layout)
        layout.addWidget(info_group, 1)

        return frame

    def _create_top_bar(self) -> QWidget:
        """创建顶部登录/用户信息栏

        Returns:
            顶部栏控件
        """
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        frame.setStyleSheet("background-color: #f5f4ef;")

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)

        # 左侧应用标题
        title_label = QLabel("delion智慧树")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #333;")
        layout.addWidget(title_label)

        # 弹簧
        layout.addItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        # 用户信息标签
        self.lbl_user_info = QLabel("未登录")
        self.lbl_user_info.setStyleSheet("color: #666; font-size: 13px;")
        layout.addWidget(self.lbl_user_info)

        # 登录按钮
        self.btn_login = QPushButton("登录")
        self.btn_login.setMinimumWidth(80)
        self.btn_login.setMinimumHeight(30)
        self.btn_login.setCursor(Qt.PointingHandCursor)
        self.btn_login.setStyleSheet("""
            QPushButton {
                background-color: #d97757;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 5px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c46a4a;
            }
        """)
        self.btn_login.clicked.connect(self._on_login_clicked)
        layout.addWidget(self.btn_login)

        # 退出登录按钮（初始隐藏）
        self.btn_logout = QPushButton("退出登录")
        self.btn_logout.setMinimumWidth(80)
        self.btn_logout.setMinimumHeight(30)
        self.btn_logout.setCursor(Qt.PointingHandCursor)
        self.btn_logout.setStyleSheet("""
            QPushButton {
                background-color: #ccc;
                color: #333;
                border: none;
                border-radius: 5px;
                padding: 5px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #bbb;
            }
        """)
        self.btn_logout.clicked.connect(self._on_logout_clicked)
        self.btn_logout.hide()
        layout.addWidget(self.btn_logout)

        return frame

    def _create_refresh_icon(self) -> QIcon:
        """从 SVG 创建刷新图标"""
        if getattr(sys, 'frozen', False):
            base_dir = Path(sys.executable).parent
        else:
            base_dir = Path(__file__).parent.parent
        svg_path = base_dir / "assets" / "refresh.svg"

        if svg_path.exists():
            pixmap = QPixmap(24, 24)
            pixmap.fill(Qt.transparent)

            renderer = QSvgRenderer(str(svg_path))
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()

            return QIcon(pixmap)
        else:
            pixmap = QPixmap(24, 24)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            painter.setPen(Qt.black)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.drawEllipse(2, 2, 20, 20)
            painter.drawLine(12, 6, 12, 12)
            painter.drawLine(12, 12, 16, 10)
            painter.end()
            return QIcon(pixmap)

    def _create_browser_area(self) -> QWidget:
        """创建浏览器区域

        Returns:
            浏览器区域控件
        """
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        url_layout = QHBoxLayout()
        url_layout.setSpacing(5)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("输入 URL 地址...")
        self.url_input.setMinimumHeight(35)
        self.url_input.setReadOnly(True)
        self.url_input.setFocusPolicy(Qt.NoFocus)
        self.url_input.setStyleSheet("""
            QLineEdit {
                padding-left: 8px;
                border: none;
                background-color: transparent;
            }
        """)
        self.url_input.returnPressed.connect(self.navigate_to_url)

        self.btn_refresh = QPushButton()
        self.btn_refresh.setIcon(self._create_refresh_icon())
        self.btn_refresh.setFixedSize(35, 35)
        self.btn_refresh.setToolTip("刷新页面")
        self.btn_refresh.clicked.connect(self.reload_page)
        self.btn_refresh.setStyleSheet("""
            QPushButton {
                border: none;
                background-color: transparent;
            }
            QPushButton:hover {
                background-color: rgba(0, 0, 0, 0.1);
                border-radius: 5px;
            }
        """)

        url_layout.addWidget(self.url_input)
        url_layout.addWidget(self.btn_refresh)

        layout.addLayout(url_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumHeight(3)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                background-color: transparent;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
            }
        """)
        layout.addSpacing(8)
        layout.addWidget(self.progress_bar)

        self.browser = BrowserEngine(frame)
        browser_view = self.browser.get_view()

        layout.addWidget(browser_view)

        return frame

    def _init_browser(self):
        """初始化浏览器"""
        if self.browser and self.config.url:
            self.browser.load_url(self.config.url)

    def _connect_signals(self):
        """连接信号和槽"""
        if self.browser:
            view = self.browser.get_view()
            view.loadStarted.connect(self._on_load_started)
            view.loadFinished.connect(self._on_load_finished)
            view.loadProgress.connect(self._on_load_progress)
            view.urlChanged.connect(self._on_url_changed)

    def _load_user_config(self):
        """加载用户配置"""
        account = self.ini_config.get_account()
        password = self.ini_config.get_password()
        self.auto_login_enabled = self.ini_config.get_auto_login_enabled()

        self.account_input.setText(account)
        self.password_input.setText(password)
        
        # 设置自动登录开关状态
        self.btn_auto_login_toggle.setChecked(self.auto_login_enabled)
        self._update_auto_login_ui()

    def Write_Log(self, message: str):
        """写入日志信息（供外部调用的接口）

        Args:
            message: 要写入的日志消息
        """
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.info_text.append(f"[{timestamp}] {message}")

    def _on_toggle_auto_login(self):
        """切换自动登录开关状态"""
        self.auto_login_enabled = self.btn_auto_login_toggle.isChecked()
        self.ini_config.set_auto_login_enabled(self.auto_login_enabled)
        self._update_auto_login_ui()
        
        if self.auto_login_enabled:
            self.Write_Log("自动登录已开启")
            self.logger.info("自动登录功能已开启")
            # 开启后立即检查是否需要自动登录
            self._check_auto_login()
        else:
            self.Write_Log("自动登录已关闭")
            self.logger.info("自动登录功能已关闭")

    def _update_auto_login_ui(self):
        """根据自动登录开关状态更新UI"""
        if self.auto_login_enabled:
            self.btn_auto_login_toggle.setText("自动登录已开启")
        else:
            self.btn_auto_login_toggle.setText("自动登录已关闭")
        # 账户和密码始终保持显示

    def _set_form_row_visible(self, widget, visible):
        """设置表单布局中某行的可见性"""
        # 获取widget的标签
        config_group = self.account_input.parent()
        if config_group:
            form_layout = config_group.layout()
            if isinstance(form_layout, QFormLayout):
                for i in range(form_layout.rowCount()):
                    label_item = form_layout.itemAt(i, QFormLayout.LabelRole)
                    field_item = form_layout.itemAt(i, QFormLayout.FieldRole)
                    if field_item and field_item.widget() == widget:
                        if label_item and label_item.widget():
                            label_item.widget().setVisible(visible)
                        break

    def _on_save_config(self):
        """保存配置文件"""
        account = self.account_input.text()
        password = self.password_input.text()

        self.ini_config.set_account(account)
        self.ini_config.set_password(password)
        # 保存自动登录开关状态
        self.ini_config.set_auto_login_enabled(self.auto_login_enabled)

        self.Write_Log("配置文件保存成功")

    @Slot()
    def navigate_to_url(self):
        """导航到 URL"""
        url = self.url_input.text().strip()
        if url:
            if not url.startswith('http://') and not url.startswith('https://'):
                url = 'https://' + url
            self.browser.load_url(url)
            self.Write_Log(f"正在加载: {url}")

    @Slot()
    def reload_page(self):
        """刷新页面"""
        if self.browser:
            self.browser.get_view().reload()
            self.Write_Log("刷新页面")

    def _auto_login(self):
        """自动登录功能"""
        if self.is_logging_in:
            return

        account = self.account_input.text().strip()
        password = self.password_input.text().strip()

        if not account or not password:
            self.Write_Log("账户或密码为空，跳过自动登录")
            return

        self.is_logging_in = True
        self._login_check_attempts = 0
        self._max_login_attempts = 30  # 最多检查30次
        self.Write_Log("开始自动登录...")

        login_script = f"""
        (function() {{
            // 输入账户
            var usernameInput = document.getElementById('lUsername');
            if (usernameInput) {{
                usernameInput.value = '{account}';
                usernameInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                usernameInput.dispatchEvent(new Event('change', {{ bubbles: true }}));
            }}

            // 输入密码
            var passwordInput = document.getElementById('lPassword');
            if (passwordInput) {{
                passwordInput.value = '{password}';
                passwordInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                passwordInput.dispatchEvent(new Event('change', {{ bubbles: true }}));
            }}

            // 点击登录按钮
            var loginBtn = document.querySelector('.wall-sub-btn');
            if (loginBtn) {{
                loginBtn.click();
            }}
        }})();
        """

        self.browser.run_javascript(login_script)

        QTimer.singleShot(2000, self._check_login_result)

    def _check_login_result(self):
        """检查登录结果，检测验证码弹窗或登录是否成功"""
        check_script = """
        (function() {
            var url = window.location.href;
            var modal = document.querySelector('.yidun_modal');
            
            // 检查验证码弹窗
            if (modal && modal.style.display !== 'none' && modal.offsetParent !== null) {
                return 'verify_slider';
            }
            
            // 检查是否还在登录页面
            var isLoginPage = url.includes('passport') || url.includes('login') || url.includes('signin');
            
            // 检查是否有登录表单（说明还没登录）
            var hasLoginForm = document.getElementById('lUsername') !== null || document.querySelector('.login') !== null;
            
            // 只有不在登录页面且没有登录表单，才认为登录成功
            if (!isLoginPage && !hasLoginForm) {
                return 'login_success';
            }
            
            // 还在登录页面，可能正在加载，等待一下
            return 'still_on_login_page';
        })();
        """

        self.browser.run_javascript(check_script, self._on_check_login_result)

    def _on_check_login_result(self, result):
        """登录结果回调"""
        if result == 'verify_slider':
            # 只有在 is_logging_in 为 True 时才处理验证码
            if not self.is_logging_in:
                self.Write_Log("登录已取消，停止验证")
                return
            self.Write_Log("检测到验证码弹窗，开始处理滑块验证...")
            self.verify_attempt = 0
            self._handle_slider_verification()
        elif result == 'still_on_login_page':
            # 还在登录页面，检查是否超时
            self._login_check_attempts += 1
            if self._login_check_attempts >= self._max_login_attempts:
                self.Write_Log("登录等待超时，请检查网络或手动登录")
                self.is_logging_in = False
                return
            
            self.Write_Log(f"还在登录页面，继续等待登录状态变化... ({self._login_check_attempts}/{self._max_login_attempts})")
            QTimer.singleShot(1500, self._check_login_result)
        elif result == 'login_success':
            # self.Write_Log("登录完成")
            self.is_logging_in = False
            self._after_login_success()
        else:
            # 未知状态，默认继续等待，同时检查超时
            self._login_check_attempts += 1
            if self._login_check_attempts >= self._max_login_attempts:
                self.Write_Log("登录等待超时，请检查网络或手动登录")
                self.is_logging_in = False

    def _check_verify_complete(self, app_url: str, check_count: int = 0):
        """检查安全验证是否完成"""
        if check_count >= 60:  # 最多检查60次（约2分钟）
            self.Write_Log("验证等待超时，请手动返回刷课页面")
            return
        
        # 检查页面是否还包含安全验证弹窗
        check_script = """
        (function() {
            var modal = document.querySelector('.yidun_modal__wrap');
            var smsBox = document.querySelector('.yidun_smsbox');
            if (modal && smsBox) {
                return 'verify_present';
            }
            return 'verify_absent';
        })();
        """
        
        def on_check_result(result):
            if result == 'verify_absent':
                # 安全验证已完成，返回刷课页面
                self.Write_Log("安全验证已完成，返回刷课页面...")
                if self.browser:
                    self.browser.load_url(app_url)
            else:
                # 安全验证仍在，继续检查
                QTimer.singleShot(2000, lambda: self._check_verify_complete(app_url, check_count + 1))
        
        if self.browser:
            self.browser.run_javascript(check_script, on_check_result)
            return
            
            self.Write_Log(f"收到未知状态: {result}，继续等待... ({self._login_check_attempts}/{self._max_login_attempts})")
            QTimer.singleShot(1500, self._check_login_result)

    def _start_verify_check_after_load(self, course_url: str):
        """在页面加载完成后开始检测安全验证"""
        if not self.browser or not course_url:
            return
        
        view = self.browser.get_view()
        
        # 定义加载完成回调
        def on_load_finished(ok):
            # 断开信号，避免重复触发
            view.loadFinished.disconnect(on_load_finished)
            if ok:
                self.Write_Log("验证页面加载完成，开始检测安全验证...")
                # 延迟2秒确保页面完全渲染
                from PySide6.QtCore import QTimer
                QTimer.singleShot(2000, lambda: self._check_verify_complete(course_url))
            else:
                self.Write_Log("验证页面加载失败")
        
        # 连接信号
        view.loadFinished.connect(on_load_finished)

    def _handle_slider_verification(self):
        """处理滑块验证码 - 使用 qasync"""
        # 首先检查是否还在登录中或处于冷却状态
        if not self.is_logging_in:
            return
        if getattr(self, '_slider_verify_cool_down', False):
            return
        
        if not self.slider_verifier:
            self.Write_Log("滑块验证器未初始化，无法自动处理滑块验证")
            self.is_logging_in = False
            return

        if not self.browser:
            self.Write_Log("浏览器引擎未初始化")
            self.is_logging_in = False
            return

        if self.verify_attempt >= 3:
            self.Write_Log("自动验证尝试次数过多，请手动验证")
            self.is_logging_in = False
            return

        self.verify_attempt += 1
        self.Write_Log(f"第{self.verify_attempt}次尝试滑块验证...")

        # 设置浏览器引擎
        self.slider_verifier.set_browser_engine(self.browser)

        # 创建异步任务执行验证 - 使用 qasync
        async def run_verification():
            try:
                # 在异步任务中也检查登录状态
                if not self.is_logging_in:
                    self.Write_Log("登录已取消，停止验证")
                    return
                    
                success = await self.slider_verifier.verify(max_attempts=3, offset=10)
                
                # 检查登录状态（可能在等待期间变为 False）
                if not self.is_logging_in:
                    self.Write_Log("登录已取消，停止验证")
                    return
                    
                if success:
                    self.Write_Log("滑块验证成功，尝试重新登录...")
                    self.browser.run_javascript("""
                        (function() {
                            var loginBtn = document.querySelector('.wall-sub-btn');
                            if (loginBtn) loginBtn.click();
                        })();
                    """)
                    QTimer.singleShot(2000, self._check_login_result)
                else:
                    if self.verify_attempt < 3 and self.is_logging_in:
                        self.Write_Log("验证失败，重试...")
                        QTimer.singleShot(500, self._handle_slider_verification)
                    else:
                        self.Write_Log("自动验证尝试次数过多，请手动验证")
                        self.is_logging_in = False
            except Exception as e:
                self.Write_Log(f"验证过程出错: {e}")
                self.is_logging_in = False

        # 使用当前 qasync 事件循环运行任务
        import asyncio
        asyncio.create_task(run_verification())

    def _after_login_success(self):
        """登录成功后处理：仅获取并保存用户信息，不自动跳转页面"""
        # 防止重复执行
        if self._login_success_handled:
            return
        
        if not self.slider_verifier:
            self.Write_Log("滑块验证器未初始化，无法获取课程信息")
            return
        
        if not self.browser:
            self.Write_Log("浏览器引擎未初始化，无法获取课程信息")
            return
        
        # 标记已处理
        self._login_success_handled = True
        
        # 停止扫码登录检测（如果正在运行）
        if hasattr(self, '_scan_login_timer') and self._scan_login_timer.isActive():
            self._scan_login_timer.stop()
        
        # 停止滑块验证循环
        self.is_logging_in = False
        self.verify_attempt = 0
        # 添加一个冷却标志，防止旧的计时器触发
        self._slider_verify_cool_down = True
        # 延迟清除冷却标志
        from PySide6.QtCore import QTimer
        QTimer.singleShot(3000, lambda: setattr(self, '_slider_verify_cool_down', False))
        
        # 设置浏览器引擎给滑块验证器
        self.slider_verifier.set_browser_engine(self.browser)

        self.Write_Log("登录成功，开始获取用户信息...")

        async def get_user_info():
            try:
                # 1. 先获取 Cookie
                cookie = await self.slider_verifier.Access_to_public_courses_cookie()
                if not cookie:
                    # 浏览器获取失败，尝试从缓存获取
                    cookie = get_saved_cookie()
                    if not cookie:
                        self.Write_Log("无法获取 Cookie")
                        return
                    self.Write_Log("从缓存中获取到 Cookie")

                # 保存 cookie 到缓存
                save_cookie_one(cookie)

                # 2. 获取用户信息
                from modules.user import user_value
                user_result = user_value(cookie)
                
                real_name = user_result.get("realName")
                
                if real_name:
                    self.Write_Log("")
                    self.Write_Log("^ ̳> ·̫ < ̳^")                    
                    self.Write_Log(f"欢迎{real_name}同学")
                    self.Write_Log("^ >𖥦< ^ ੭")
                    self.Write_Log("")
                    self.Write_Log("登录成功！请点击[刷课]按钮开始学习")
                    
                    # 保存用户名供后续使用
                    self._current_user_name = real_name
                    self._current_cookie = cookie
                else:
                    self.Write_Log("无法获取用户信息")
                    self.logger.warning("用户信息获取失败")

            except Exception as e:
                self.Write_Log(f"获取信息失败: {e}")
                self.logger.error(f"获取信息失败: {e}")

        import asyncio
        asyncio.create_task(get_user_info())
    
    async def _switch_to_local_page(self, username: str):
        """通过自定义 scheme 访问内置页面"""
        if not self.browser:
            self.Write_Log("浏览器引擎未初始化，无法切换页面")
            return
        
        try:
            # 通过自定义 scheme URL 访问（用户名已嵌入 URL）
            app_url = app_web.get_app_url(username)
            self._current_course_url = app_url  # 保存刷课页面 URL
            self.browser.load_url(app_url)
            # self.Write_Log(f"已切换到内置页面: {app_url}")

            # 设置课程点击回调
            app_web.set_course_click_handler(self._on_course_selected)
            app_web.set_video_report_handler(self._on_video_report)
            app_web.set_batch_report_handler(self._on_batch_report)
            app_web.set_request_courses_handler(self._on_request_courses)
        except Exception as e:
            self.Write_Log(f"切换页面失败: {e}")
            self.logger.error(f"切换页面失败: {e}")
    
    async def _on_request_courses(self):
        """前端请求课程数据时的回调"""
        if hasattr(self, '_cached_course_data') and self._cached_course_data:
            # 发送缓存的课程数据
            await app_web.send_ws_message("Refresh-课程", self._cached_course_data)
            # self.Write_Log("已发送缓存的课程数据")
        elif hasattr(self, '_cached_cookie') and self._cached_cookie:
            # 如果没有缓存数据但有 cookie，则重新获取
            self.Write_Log("正在重新获取课程列表...")
            try:
                result = await self.slider_verifier.Access_to_public_courses_date(self._cached_cookie)
                if result.courses:
                    course_data = [
                        {
                            "name": c.course_name,
                            "progress": c.progress,
                            "secret": c.secret
                        }
                        for c in result.courses
                    ]
                    self._cached_course_data = course_data
                    await app_web.send_ws_message("Refresh-课程", course_data)
            except Exception as e:
                self.Write_Log(f"重新获取课程失败: {e}")

    async def _on_course_selected(self, secret: str):
        """课程被点击选择时的回调"""
        try:
            if not self.slider_verifier:
                self.Write_Log("滑块验证器未初始化")
                return
            
            if not self.browser:
                self.Write_Log("浏览器引擎未初始化")
                return
            
            # 保存 secret 供刷新使用
            self._report_secret = secret
            
            # 设置浏览器引擎
            self.slider_verifier.set_browser_engine(self.browser)

            # 获取 Cookie
            cookie = await self.slider_verifier.Access_to_public_courses_cookie()
            if not cookie:
                cookie = get_saved_cookie()
                if not cookie:
                    self.Write_Log("无法获取 Cookie")
                    return

            # 调用 videos.py 获取视频信息
            from modules.videos import video_cookie_one

            def fetch_videos():
                return video_cookie_one(cookie, secret)

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, fetch_videos)

            # 提取 recruitId、courseId
            video_data = result.get("videos", {}).get("data", {})
            recruit_id = video_data.get("recruitId")
            course_id = video_data.get("courseId")

            # 获取 uuid（从 CASLOGC cookie 中解析）
            import urllib.parse
            import json
            uuid = ""
            cookies_dict = {}
            for part in cookie.split(';'):
                part = part.strip()
                if '=' in part:
                    k, v = part.split('=', 1)
                    cookies_dict[k.strip()] = v.strip()
            caslogc = cookies_dict.get("CASLOGC", "")
            # self.Write_Log(f"CASLOGC原始值: {caslogc[:50] if caslogc else '未找到'}")
            if caslogc:
                try:
                    decoded = urllib.parse.unquote(caslogc)
                    cas_data = json.loads(decoded)
                    uuid = cas_data.get("uuid", "")
                    # self.Write_Log(f"uuid解析结果: {uuid}")
                except Exception as e:
                    self.Write_Log(f"CASLOGC解析失败: {e}")
            else:
                self.Write_Log("Cookie中未找到CASLOGC")

            # 保存供上报使用
            self._report_cookie = cookie
            self._report_recruit_id = recruit_id
            self._report_course_id = course_id
            self._report_uuid = uuid

            # self.Write_Log(f"课程参数已保存 - recruitId: {recruit_id}, courseId: {course_id}, uuid: {uuid}")

            # 解析视频列表并推送给前端（按章节组织，附带完整元数据）
            chapters = []
            video_chapters = video_data.get("videoChapterDtos", [])
            study_info = result.get("study_info", {})

            for chapter in video_chapters:
                chapter_name = chapter.get("name", "未知章节")
                chapter_videos = []

                for lesson in chapter.get("videoLessons", []):
                    lesson_id = str(lesson.get("id", ""))
                    lesson_name = lesson.get("name", "")
                    chapter_id = str(lesson.get("chapterId", ""))

                    if lesson.get("ishaveChildrenLesson", False):
                        for small in lesson.get("videoSmallLessons", []):
                            small_id = str(small.get("id", ""))
                            small_name = small.get("name", "")
                            video_info = study_info.get(small_id, {})
                            watch_state = video_info.get("watchState", 0)
                            chapter_videos.append({
                                "name": small_name,
                                "status": "已完成" if watch_state == 1 else "未完成",
                                # 上报所需的元数据
                                "bigLessionId": lesson_id,
                                "smallLessionId": small_id,
                                "videoId": str(small.get("videoId", "")),
                                "chapterId": chapter_id,
                                "videoSec": small.get("videoSec", 0),
                            })
                    else:
                        video_info = study_info.get(lesson_id, {})
                        watch_state = video_info.get("watchState", 0)
                        chapter_videos.append({
                            "name": lesson_name,
                            "status": "已完成" if watch_state == 1 else "未完成",
                            # 上报所需的元数据
                            "bigLessionId": lesson_id,
                            "smallLessionId": "0",
                            "videoId": str(lesson.get("videoId", "")),
                            "chapterId": chapter_id,
                            "videoSec": lesson.get("videoSec", 0),
                        })

                chapters.append({
                    "name": chapter_name,
                    "videos": chapter_videos
                })

            await app_web.send_ws_message("Select-视频", chapters)

        except Exception as e:
            self.Write_Log(f"获取视频信息失败: {e}")
            self.logger.error(f"获取视频信息失败: {e}")

    async def _refresh_video_list(self):
        """刷新视频列表（队列完成后调用）"""
        try:
            # 获取已保存的参数
            secret = getattr(self, '_report_secret', None)
            cookie = getattr(self, '_report_cookie', None)

            if not secret or not cookie:
                return

            # 调用 videos.py 获取最新视频信息
            from modules.videos import video_cookie_one

            def fetch_videos():
                return video_cookie_one(cookie, secret)

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, fetch_videos)

            video_data = result.get("videos", {}).get("data", {})
            study_info = result.get("study_info", {})

            # 解析视频列表
            chapters = []
            video_chapters = video_data.get("videoChapterDtos", [])

            for chapter in video_chapters:
                chapter_name = chapter.get("name", "未知章节")
                chapter_videos = []

                for lesson in chapter.get("videoLessons", []):
                    lesson_id = str(lesson.get("id", ""))
                    lesson_name = lesson.get("name", "")
                    chapter_id = str(lesson.get("chapterId", ""))

                    if lesson.get("ishaveChildrenLesson", False):
                        for small in lesson.get("videoSmallLessons", []):
                            small_id = str(small.get("id", ""))
                            small_name = small.get("name", "")
                            video_info = study_info.get(small_id, {})
                            watch_state = video_info.get("watchState", 0)
                            chapter_videos.append({
                                "name": small_name,
                                "status": "已完成" if watch_state == 1 else "未完成",
                                "bigLessionId": lesson_id,
                                "smallLessionId": small_id,
                                "videoId": str(small.get("videoId", "")),
                                "chapterId": chapter_id,
                                "videoSec": small.get("videoSec", 0),
                            })
                    else:
                        video_info = study_info.get(lesson_id, {})
                        watch_state = video_info.get("watchState", 0)
                        chapter_videos.append({
                            "name": lesson_name,
                            "status": "已完成" if watch_state == 1 else "未完成",
                            "bigLessionId": lesson_id,
                            "smallLessionId": "0",
                            "videoId": str(lesson.get("videoId", "")),
                            "chapterId": chapter_id,
                            "videoSec": lesson.get("videoSec", 0),
                        })

                chapters.append({
                    "name": chapter_name,
                    "videos": chapter_videos
                })

            # 推送更新后的视频列表到前端
            await app_web.send_ws_message("Select-视频", chapters)

        except Exception as e:
            self.Write_Log(f"刷新视频列表失败: {e}")
            self.logger.error(f"刷新视频列表失败: {e}")

    async def _on_video_report(self, video_data: dict):
        """处理视频进度上报：用户点击视频后调用 Report_progress 上报"""
        try:
            video_name = video_data.get("name", "未知视频")
            video_sec = video_data.get("videoSec", 0)
            status = video_data.get("status", "")

            # 检查队列是否正在运行
            from modules.Line_up import is_queue_running
            if is_queue_running():
                self.Write_Log(f"⚠️ 队列正在运行中，请等待队列完成后再执行单任务")
                return

            self.Write_Log(f"开始刷课: {video_name}（{video_sec}秒）")

            if status == "已完成":
                self.Write_Log(f"该视频已完成，跳过: {video_name}")
                return

            # 获取保存的上报参数
            cookie = getattr(self, '_report_cookie', None)
            recruit_id = getattr(self, '_report_recruit_id', None)
            course_id = getattr(self, '_report_course_id', None)
            uuid = getattr(self, '_report_uuid', None)

            if not cookie or not recruit_id or not course_id or not uuid:
                missing = []
                if not cookie: missing.append("cookie")
                if not recruit_id: missing.append("recruitId")
                if not course_id: missing.append("courseId")
                if not uuid: missing.append("uuid")
                self.Write_Log(f"上报参数缺失: {', '.join(missing)}，请重新选择课程")
                return

            # 设置 Report_progress 参数
            from modules.Report_progress import (
                Report_progress_cookie_one,
                Report_progress_recruitId,
                Report_progress_courseId,
                Report_progress_uuid,
                Report_progress_bigLessionId,
                Report_progress_smallLessionId,
                Report_progress_videoId,
                Report_progress_chapterId,
                Report_progress_videoSec,
                Report_progress_Progress,
                Report_progress_video_name,
                Report_progress_set_callback,
                Report_progress_Output,
            )

            Report_progress_cookie_one(cookie)
            Report_progress_recruitId(recruit_id)
            Report_progress_courseId(course_id)
            Report_progress_uuid(uuid)
            Report_progress_bigLessionId(int(video_data.get("bigLessionId", 0)))
            Report_progress_smallLessionId(int(video_data.get("smallLessionId", 0)))
            Report_progress_video_name(video_name)
            Report_progress_videoId(int(video_data.get("videoId", 0)))
            Report_progress_chapterId(int(video_data.get("chapterId", 0)))
            Report_progress_videoSec(int(video_sec))
            Report_progress_Progress(10)

            # 设置进度回调（通过信号跨线程安全更新 UI）
            def on_progress(current, total, api_result=None):
                # 过滤掉无效的进度值（如 -1/-1）
                if current < 0 or total <= 0:
                    return
                    
                percent = round(current / total * 100, 1) if total > 0 else 0
                log_msg = f"进度: {current}/{total}秒（{percent}%）"
                self.progress_log.emit(log_msg)

            Report_progress_set_callback(on_progress)

            # 在线程池中执行上报（避免阻塞）
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, Report_progress_Output)

            if result == -1:
                self.Write_Log(f"上报失败: {video_name}")
                self.Write_Log("⚠️ 请解除当前验证")
                # 跳转到验证页面并开始检测验证完成
                if self.browser and hasattr(self, '_report_secret'):
                    secret = self._report_secret
                    verify_url = f"https://studyvideoh5.zhihuishu.com/stuStudy?recruitAndCourseId={secret}"
                    course_url = getattr(self, '_current_course_url', None)
                    # 使用 loadFinished 信号确保页面加载完成后再检测
                    self._start_verify_check_after_load(course_url)
                    self.browser.load_url(verify_url)
            elif isinstance(result, dict):
                # 在终端打印接口返回状态码
                result_code = result.get("code", 0)
                result_message = result.get("message", "")
                print(f"[上报进度] code={result_code}, message={result_message}")
                
                # 检查是否是需要验证的失败情况
                if result_code == -1 and "上报失败，已停止" in result_message:
                    self.Write_Log(f"⚠️ 上报失败: {video_name}")
                    self.Write_Log("⚠️ 请解除当前验证")
                    # 跳转到验证页面并开始检测验证完成
                    if self.browser and hasattr(self, '_report_secret'):
                        secret = self._report_secret
                        verify_url = f"https://studyvideoh5.zhihuishu.com/stuStudy?recruitAndCourseId={secret}"
                        course_url = getattr(self, '_current_course_url', None)
                        # 使用 loadFinished 信号确保页面加载完成后再检测
                        self._start_verify_check_after_load(course_url)
                        self.browser.load_url(verify_url)
                elif result_code == -2:
                    # 检测到重复上报
                    self.Write_Log(f"⚠️ 检测到重复上报！当前有视频正在处理中")
                    self.Write_Log(f"   请等待当前视频处理完成后再点击")
                elif result_message == "already completed":
                    self.Write_Log(f"已完成: {video_name}")
                else:
                    self.Write_Log(f"完成: {video_name}")
                    # 部分更新：只更新单个视频状态
                    video_id = video_data.get("videoId")
                    if video_id:
                        asyncio.create_task(app_web.send_ws_message("Update-视频状态", {
                            "videoId": video_id,
                            "status": "已完成"
                        }))

        except Exception as e:
            self.Write_Log(f"视频上报异常: {e}")
            self.logger.error(f"视频上报异常: {e}")

    async def _on_batch_report(self, data: dict):
        """处理批量视频上报：将视频列表加入队列排队执行"""
        try:
            videos = data.get("videos", [])
            if not videos:
                self.Write_Log("批量上报：未收到视频数据")
                return

            # 过滤已完成的视频
            undone_videos = [v for v in videos if v.get("status") != "已完成"]
            if not undone_videos:
                self.Write_Log("批量上报：所选视频均已完成")
                return

            self.Write_Log(f"批量刷课：已加入 {len(undone_videos)} 个视频到队列")

            # 导入队列模块
            from modules.Line_up import (
                enqueue,
                start_queue,
                set_on_next_handler,
                set_on_queue_empty_handler,
                set_on_clear_handler,
                clear_queue,
            )

            # 设置队列的下一个视频处理回调
            async def on_next_video(video, index, total):
                """队列中每个视频的处理回调"""
                video_name = video.get("name", "未知视频")
                self.Write_Log(f"队列 [{index + 1}/{total}]：开始刷课 {video_name}")

                # 发送队列状态更新到前端（第一个视频显示覆盖层，后续更新进度）
                await app_web.send_ws_message("Queue-状态更新", {
                    "running": True,
                    "total": total,
                    "current": index + 1,
                    "videoName": video_name,
                    "update": index > 0  # true表示更新进度，false表示首次显示
                })

                # 调用现有的单个视频上报逻辑
                result = await self._process_single_video(video)

                return result

            # 队列清空回调（正常完成或安全验证触发）
            async def on_queue_empty():
                self.Write_Log("队列处理结束")
                # 发送队列结束状态到前端（隐藏覆盖层）
                await app_web.send_ws_message("Queue-状态更新", {
                    "running": False,
                    "total": 0,
                    "current": 0,
                    "videoName": ""
                })
                # 重置前端按钮状态
                await app_web.send_ws_message("Batch-队列结束", {})
                # 刷新视频列表数据
                if hasattr(self, '_report_secret') and self._report_secret:
                    await self._refresh_video_list()

            # 安全验证清空回调
            def on_clear(removed_count):
                self.Write_Log(f"安全验证触发，队列已清空（移除 {removed_count} 个待处理视频）")
                # 发送队列结束状态到前端（隐藏覆盖层）
                asyncio.create_task(app_web.send_ws_message("Queue-状态更新", {
                    "running": False,
                    "total": 0,
                    "current": 0,
                    "videoName": ""
                }))

            set_on_next_handler(on_next_video)
            set_on_queue_empty_handler(on_queue_empty)
            set_on_clear_handler(on_clear)

            # 将视频加入队列并启动
            enqueue(undone_videos)
            await start_queue()

        except Exception as e:
            self.Write_Log(f"批量上报异常: {e}")
            self.logger.error(f"批量上报异常: {e}")

    async def _process_single_video(self, video_data: dict) -> dict:
        """处理单个视频的上报（供队列和单独点击共用）

        Returns:
            dict: 上报结果 {"code": ..., "message": ...}
        """
        video_name = video_data.get("name", "未知视频")
        video_sec = video_data.get("videoSec", 0)
        status = video_data.get("status", "")

        if status == "已完成":
            self.Write_Log(f"该视频已完成，跳过: {video_name}")
            return {"code": 0, "message": "already completed"}

        # 获取保存的上报参数
        cookie = getattr(self, '_report_cookie', None)
        recruit_id = getattr(self, '_report_recruit_id', None)
        course_id = getattr(self, '_report_course_id', None)
        uuid = getattr(self, '_report_uuid', None)

        if not cookie or not recruit_id or not course_id or not uuid:
            missing = []
            if not cookie: missing.append("cookie")
            if not recruit_id: missing.append("recruitId")
            if not course_id: missing.append("courseId")
            if not uuid: missing.append("uuid")
            self.Write_Log(f"上报参数缺失: {', '.join(missing)}，请重新选择课程")
            return {"code": -1, "message": f"上报参数缺失: {', '.join(missing)}"}

        # 设置 Report_progress 参数
        from modules.Report_progress import (
            Report_progress_cookie_one,
            Report_progress_recruitId,
            Report_progress_courseId,
            Report_progress_uuid,
            Report_progress_bigLessionId,
            Report_progress_smallLessionId,
            Report_progress_videoId,
            Report_progress_chapterId,
            Report_progress_videoSec,
            Report_progress_Progress,
            Report_progress_video_name,
            Report_progress_set_callback,
            Report_progress_Output,
        )

        Report_progress_cookie_one(cookie)
        Report_progress_recruitId(recruit_id)
        Report_progress_courseId(course_id)
        Report_progress_uuid(uuid)
        Report_progress_bigLessionId(int(video_data.get("bigLessionId", 0)))
        Report_progress_smallLessionId(int(video_data.get("smallLessionId", 0)))
        Report_progress_video_name(video_name)
        Report_progress_videoId(int(video_data.get("videoId", 0)))
        Report_progress_chapterId(int(video_data.get("chapterId", 0)))
        Report_progress_videoSec(int(video_sec))
        Report_progress_Progress(10)

        # 设置进度回调
        def on_progress(current, total, api_result=None):
            if current < 0 or total <= 0:
                return
            percent = round(current / total * 100, 1) if total > 0 else 0
            log_msg = f"进度: {current}/{total}秒（{percent}%）"
            self.progress_log.emit(log_msg)

        Report_progress_set_callback(on_progress)

        # 在线程池中执行上报
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, Report_progress_Output)

        if result == -1:
            self.Write_Log(f"上报失败: {video_name}")
            self.Write_Log("⚠️ 请解除当前验证")
            # 跳转到验证页面
            if self.browser and hasattr(self, '_report_secret'):
                secret = self._report_secret
                verify_url = f"https://studyvideoh5.zhihuishu.com/stuStudy?recruitAndCourseId={secret}"
                course_url = getattr(self, '_current_course_url', None)
                self._start_verify_check_after_load(course_url)
                self.browser.load_url(verify_url)
            return {"code": -1, "message": "上报失败，已停止"}
        elif isinstance(result, dict):
            result_code = result.get("code", 0)
            result_message = result.get("message", "")

            if result_code == -1 and "上报失败，已停止" in result_message:
                self.Write_Log(f"⚠️ 上报失败: {video_name}")
                self.Write_Log("⚠️ 请解除当前验证")
                if self.browser and hasattr(self, '_report_secret'):
                    secret = self._report_secret
                    verify_url = f"https://studyvideoh5.zhihuishu.com/stuStudy?recruitAndCourseId={secret}"
                    course_url = getattr(self, '_current_course_url', None)
                    self._start_verify_check_after_load(course_url)
                    self.browser.load_url(verify_url)
                return {"code": -1, "message": "上报失败，已停止"}
            elif result_code == -2:
                self.Write_Log(f"⚠️ 检测到重复上报！当前有视频正在处理中")
                return {"code": -2, "message": "检测到重复上报"}
            elif result_code == -3:
                # 队列正在运行中
                self.Write_Log(f"⚠️ 队列正在运行中，请等待队列完成后再执行单任务")
                return {"code": -3, "message": "队列正在运行中，请等待队列完成"}
            elif result_message == "already completed":
                self.Write_Log(f"已完成: {video_name}")
                return {"code": 0, "message": "already completed"}
            else:
                self.Write_Log(f"完成: {video_name}")
                video_id = video_data.get("videoId")
                if video_id:
                    asyncio.create_task(app_web.send_ws_message("Update-视频状态", {
                        "videoId": video_id,
                        "status": "已完成"
                    }))
                return {"code": 0, "message": "completed"}

        return {"code": -1, "message": "未知结果"}

    @Slot()
    def on_course_clicked(self):
        """刷课按钮点击事件：获取课程信息并切换到本地页面"""
        self.logger.info("触发刷课功能")
        self.Write_Log("刷课功能启动")
        
        async def start_course_study():
            try:
                # 检查浏览器引擎
                if not self.browser:
                    self.Write_Log("浏览器引擎未初始化")
                    return
                
                if not self.slider_verifier:
                    self.Write_Log("滑块验证器未初始化")
                    return
                
                # 检查是否有保存的用户信息
                if not hasattr(self, '_current_cookie') or not self._current_cookie:
                    self.Write_Log("请先登录后再点击刷课")
                    return
                
                # 设置浏览器引擎
                self.slider_verifier.set_browser_engine(self.browser)
                
                # 启动 WebSocket 服务器（如果尚未启动）
                await app_web.start_ws_server()
                
                cookie = self._current_cookie
                real_name = getattr(self, '_current_user_name', '用户')
                
                # 1. 切换到本地页面
                self.Write_Log("正在切换到课程页面...")
                await self._switch_to_local_page(real_name)
                
                # 2. 获取课程信息
                self.Write_Log("正在获取课程列表...")
                result = await self.slider_verifier.Access_to_public_courses_date(cookie)
                
                if result.all_completed:
                    self.Write_Log("所有课程已完成")
                elif result.selected_course:
                    # self.Write_Log(f"课程进度: {result.selected_course.progress}%")
                    pass
                else:
                    self.Write_Log("未找到可学习的课程")
                
                # 3. 通过 WebSocket 将课程列表推送给前端
                if result.courses:
                    course_data = [
                        {
                            "name": c.course_name,
                            "progress": c.progress,
                            "secret": c.secret
                        }
                        for c in result.courses
                    ]
                    # 保存课程数据供重新请求时使用
                    self._cached_course_data = course_data
                    self._cached_cookie = cookie
                    await app_web.send_ws_message("Refresh-课程", course_data)
                    # self.Write_Log(f"已加载 {len(course_data)} 门课程")
                
            except Exception as e:
                self.Write_Log(f"刷课启动失败: {e}")
                self.logger.error(f"刷课启动失败: {e}")
        
        import asyncio
        asyncio.create_task(start_course_study())

    @Slot()
    def on_exam_clicked(self):
        """刷题按钮点击事件 - 开源版本不支持"""
        QMessageBox.information(
            self,
            "功能提示",
            "开源版本只提供刷课功能\n如需要完整功能请前往 zhs.shaoxin.top 中获取"
        )
    


    @Slot()
    def _on_load_started(self):
        """页面开始加载"""
        self.load_started.emit()
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

    @Slot(bool)
    def _on_load_finished(self, success: bool):
        """页面加载完成"""
        self.load_finished.emit(success)
        self.progress_bar.setVisible(False)
        self.progress_bar.setValue(0)

        if success:
            self.Write_Log("页面加载成功")
            # 登录成功后不再重复检查
            if not self._login_success_handled:
                QTimer.singleShot(2000, self._check_auto_login)  # 增加延迟到 2 秒
        else:
            self.Write_Log("页面加载失败")

    def _check_auto_login(self):
        """检查是否需要自动登录，同时启动扫码登录检测"""
        # 检查浏览器引擎是否已初始化
        if not self.browser:
            self.Write_Log("浏览器引擎未初始化，跳过登录检测")
            return
        
        # 设置浏览器引擎
        self.cookie_checker.set_browser_engine(self.browser)
        
        # 创建异步任务检查登录状态
        async def check_and_login():
            # 先等待页面真正加载完成
            # self.Write_Log("等待页面加载完成...")
            await self._wait_page_loaded()
            
            # 通过 Cookie 判断是否已经登录
            has_cookies = await self.cookie_checker.check_login_cookies()
            
            if has_cookies:
                self._after_login_success()
                return
            
            # 如果自动登录开关未开启，启动扫码登录检测
            if not self.auto_login_enabled:
                self.Write_Log("自动登录功能已关闭，等待扫码登录...")
                self._start_scan_login_monitor()
                return
            
            # === 以下为自动登录模式，不触发扫码监听 ===
            
            # 获取当前页面信息
            page_info = await self._get_page_info()
            is_login_page = page_info.get('isLoginPage', False)
            
            # 只有在登录页面时才尝试自动登录
            if not is_login_page:
                return
            
            # 检查登录页面的账号密码输入框是否已有内容
            input_status = await self._get_login_input_status()
            username_has_value = input_status.get('usernameHasValue', False)
            password_has_value = input_status.get('passwordHasValue', False)
            
            if username_has_value or password_has_value:
                return
            
            account = self.ini_config.get_account()
            password = self.ini_config.get_password()

            if account and password:
                self.Write_Log("自动登录功能已开启，开始自动登录")
                self._auto_login()
        
        asyncio.create_task(check_and_login())
    
    def _start_scan_login_monitor(self):
        """启动扫码登录检测定时器"""
        self.Write_Log("正在监听扫码登录状态...")
        self._scan_login_timer = QTimer(self)
        self._scan_login_timer.timeout.connect(self._check_scan_login_status)
        self._scan_login_timer.start(2000)  # 每2秒检查一次
        self._scan_login_attempts = 0
        self._max_scan_attempts = 150  # 最多检查5分钟（150 * 2秒）
    
    def _check_scan_login_status(self):
        """检查扫码登录是否成功（通过Cookie判断）"""
        self._scan_login_attempts += 1
        
        if self._scan_login_attempts > self._max_scan_attempts:
            self.Write_Log("扫码登录监听超时，请刷新页面重试")
            self._scan_login_timer.stop()
            return
        
        async def check_status():
            # 通过 Cookie 判断是否登录成功
            has_cookies = await self.cookie_checker.check_login_cookies()
            
            if has_cookies:
                self._scan_login_timer.stop()
                self._after_login_success()
        
        import asyncio
        asyncio.create_task(check_status())
    
    async def _get_login_input_status(self) -> dict:
        """获取登录页输入框的状态（是否有内容）"""
        if not self.browser:
            return {}
        
        script = """
        (function() {
            var usernameInput = document.getElementById('lUsername');
            var passwordInput = document.getElementById('lPassword');
            
            var usernameValue = usernameInput ? (usernameInput.value || '').trim() : '';
            var passwordValue = passwordInput ? (passwordInput.value || '').trim() : '';
            
            return JSON.stringify({
                usernameHasValue: usernameValue.length > 0,
                passwordHasValue: passwordValue.length > 0,
                usernameValue: usernameValue,
                passwordValue: passwordValue.length > 0 ? '***' : ''
            });
        })();
        """
        
        future = asyncio.Future()
        
        def callback(result):
            if not future.done():
                future.set_result(result)
        
        self.browser.run_javascript(script, callback)
        
        try:
            import json
            result_str = await asyncio.wait_for(future, timeout=3.0)
            return json.loads(result_str) if result_str else {}
        except:
            return {}
    
    async def _wait_page_loaded(self):
        """等待页面真正加载完成，包括登录页面元素"""
        import asyncio
        
        # 第一步：等待页面基本就绪
        page_ready = False
        for i in range(40):  # 最多等待20秒
            page_info = await self._get_page_info()
            if page_info.get('isReady', False):
                page_ready = True
                break
            await asyncio.sleep(0.5)
        
        if not page_ready:
            self.Write_Log("页面基本加载超时，继续执行...")
            return
        
        # self.Write_Log("页面基本就绪，检查是否需要等待登录表单...")
        
        # 第二步：如果是登录页面，等待表单元素出现
        page_info = await self._get_page_info()
        is_login_page = page_info.get('isLoginPage', False)
        
        if is_login_page:
            # 等待登录表单出现
            self.Write_Log("检测到登录页面，等待表单元素加载...")
            login_form_ready = False
            
            for i in range(20):  # 最多再等10秒
                page_info = await self._get_page_info()
                if page_info.get('hasLoginForm', False):
                    login_form_ready = True
                    break
                await asyncio.sleep(0.5)
            
            if login_form_ready:
                self.Write_Log("登录表单已就绪")
            else:
                self.Write_Log("登录表单加载超时，但将继续尝试登录")
        
        # self.Write_Log("页面准备工作完成")
    
    async def _get_page_info(self) -> dict:
        """获取页面信息"""
        if not self.browser:
            return {}
        
        script = """
        (function() {
            var url = window.location.href;
            var docReady = document.readyState === 'complete';
            var bodyExists = document.body !== null;
            var hasLoginForm = document.getElementById('lUsername') !== null || document.querySelector('.login') !== null;
            var isLoginUrl = url.includes('passport') || url.includes('login') || url.includes('signin');
            var modal = document.querySelector('.yidun_modal');
            
            return JSON.stringify({
                url: url,
                docReady: docReady,
                bodyExists: bodyExists,
                hasLoginForm: hasLoginForm,
                isLoginPage: isLoginUrl || hasLoginForm,
                hasCaptcha: !!modal,
                isReady: docReady && bodyExists
            });
        })();
        """
        
        future = asyncio.Future()
        
        def callback(result):
            if not future.done():
                future.set_result(result)
        
        self.browser.run_javascript(script, callback)
        
        try:
            import json
            result_str = await asyncio.wait_for(future, timeout=3.0)
            return json.loads(result_str) if result_str else {}
        except:
            return {}
    
    async def _check_page_ready(self) -> bool:
        """检查页面是否加载完成（保留兼容性）"""
        info = await self._get_page_info()
        return info.get('isReady', False)

    @Slot(int)
    def _on_load_progress(self, progress: int):
        """页面加载进度"""
        self.load_progress.emit(progress)
        self.progress_bar.setValue(progress)

    @Slot(QUrl)
    def _on_url_changed(self, url: QUrl):
        """URL 改变"""
        url_str = url.toString()
        self.url_input.setText(url_str)
        QTimer.singleShot(0, self._scroll_url_to_start)
        self.url_changed.emit(url_str)

    def _scroll_url_to_start(self):
        """滚动URL到开头"""
        self.url_input.setCursorPosition(0)
        self.url_input.home(False)

    def _check_and_update_login_status(self):
        """检查并更新登录状态UI"""
        if self.auth_manager.is_logged_in():
            username = self.auth_manager.get_username()
            self._auth_username = username
            self._update_login_ui(True, username)
        else:
            self._update_login_ui(False, None)

    def _update_login_ui(self, is_logged_in: bool, username: Optional[str] = None):
        """更新登录状态UI

        Args:
            is_logged_in: 是否已登录
            username: 用户名（如果已登录）
        """
        if is_logged_in and username:
            self.lbl_user_info.setText(f"欢迎, {username}")
            self.lbl_user_info.setStyleSheet("color: #d97757; font-size: 13px; font-weight: bold;")
            self.btn_login.hide()
            self.btn_logout.show()
        else:
            self.lbl_user_info.setText("未登录")
            self.lbl_user_info.setStyleSheet("color: #666; font-size: 13px;")
            self.btn_login.show()
            self.btn_logout.hide()

    @Slot()
    def _on_login_clicked(self):
        """登录按钮点击事件"""
        self.logger.info("用户点击登录")
        self.Write_Log("正在打开登录页面...")
        
        # 启动本地HTTP服务器监听回调
        asyncio.create_task(start_auth_server(self._on_auth_success_callback))
        
        # 打开登录页面，附带本地回调地址
        callback_url = "http://127.0.0.1:19960/Software/token"
        import urllib.parse
        import webbrowser
        login_url = f"https://zhs.shaoxin.top/Software/login?url={urllib.parse.quote(callback_url)}"
        webbrowser.open(login_url)

    @Slot()
    def _on_logout_clicked(self):
        """退出登录按钮点击事件"""
        reply = QMessageBox.question(
            self,
            "确认退出",
            "确定要退出登录吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.logger.info("用户退出登录")
            self.auth_manager.logout()
            self._auth_username = None
            self._login_success_handled = False  # 重置标志
            self._update_login_ui(False, None)
            self.Write_Log("已退出登录")
            
            # 重启登录服务
            try:
                from modules import start_auth_server
                import asyncio
                loop = asyncio.get_event_loop()
                loop.create_task(start_auth_server(self._on_auth_success_callback))
            except Exception as e:
                self.logger.warning(f"重启登录服务失败: {e}")

    def _on_auth_success_callback(self, username: str):
        """登录成功回调

        Args:
            username: 用户名
        """
        # 防止重复处理
        if self._login_success_handled:
            return
        
        self._login_success_handled = True
        
        self._auth_username = username
        self._update_login_ui(True, username)
        self.Write_Log("登录成功")
        self.logger.info(f"用户 {username} 登录成功")
        
        # 登录成功后关闭本地 HTTP 服务
        try:
            # 使用 QTimer 延迟调用，避免阻塞
            def _close_server():
                try:
                    loop = asyncio.get_event_loop()
                    loop.create_task(stop_auth_server())
                except Exception as e:
                    self.logger.warning(f"关闭登录服务失败: {e}")
            
            QTimer.singleShot(100, _close_server)
        except Exception as e:
            self.logger.warning(f"关闭登录服务失败: {e}")

    def closeEvent(self, event):
        """窗口关闭事件"""
        self.logger.info(f"{self.config.app_name} 已关闭")
        event.accept()
