"""
X-ZHS 打包脚本
使用 cx_Freeze 打包为 Windows 可执行文件

使用方法:
    python build.py build          # 构建可执行文件
    python build.py bdist_msi      # Windows MSI 安装包
"""
import sys
from pathlib import Path
from cx_Freeze import setup, Executable

# 项目根目录
PROJECT_ROOT = Path(__file__).parent

# 应用信息
APP_NAME = "delion-ZHS"
APP_VERSION = "1.0.0"
APP_DESCRIPTION = "智慧树学习辅助工具"

# 主入口文件
MAIN_SCRIPT = PROJECT_ROOT / "main.py"

# 需要包含的文件和目录
INCLUDE_FILES = [
    ("config.ini", "config.ini"),
    ("assets", "assets"),
    ("logs", "logs"),
    ("app.manifest", "app.manifest"),
]

# 需要包含的 Python 包
PACKAGES = [
    "cv2",
    "numpy",
    "requests",
    "qasync",
    "websockets",
    "modules",
    "components",
    "zipfile",
    "shutil",
    "pathlib",
    "http",
    "http.client",
    "http.cookiejar",
    "http.cookies",
]

# 需要排除的模块（减小体积）
EXCLUDES = [
    "tkinter",
    "unittest",
    "email",
    "xml",
    "pydoc",
    "doctest",
    "bz2",
    "lzma",
    "gzip",
    "tarfile",
    "PyQt6",
    "PyQt5",
    "PySide2",
]

# 基础构建选项
BUILD_OPTIONS = {
    "packages": PACKAGES,
    "excludes": EXCLUDES,
    "include_files": INCLUDE_FILES,
    "optimize": 2,
    "build_exe": f"build/{APP_NAME}-v{APP_VERSION}",
}

# Windows 特定选项
WINDOWS_OPTIONS = {
    "build_exe": BUILD_OPTIONS.copy(),
    "bdist_msi": {
        "upgrade_code": "{12345678-1234-1234-1234-123456789012}",
        "add_to_path": False,
        "initial_target_dir": f"[ProgramFilesFolder]\\{APP_NAME}",
    },
}

def main():
    """主构建函数"""
    if sys.platform != "win32":
        print("当前只支持 Windows 平台打包")
        return
    
    # 确保日志目录存在
    logs_dir = PROJECT_ROOT / "logs"
    logs_dir.mkdir(exist_ok=True)
    
    # 图标路径
    icon_path = PROJECT_ROOT / "assets" / "delion.ico"
    
    # 可执行文件配置
    executable = Executable(
        script=str(MAIN_SCRIPT),
        base="Win32GUI",  # Windows GUI 应用（不显示控制台）
        target_name=APP_NAME,
        icon=str(icon_path) if icon_path.exists() else None,
        shortcut_name=APP_NAME,
        shortcut_dir="DesktopFolder",
        # 启用 UAC 要求
        uac_admin=True,
    )
    
    # 执行打包
    setup(
        name=APP_NAME,
        version=APP_VERSION,
        description=APP_DESCRIPTION,
        options={
            "build_exe": WINDOWS_OPTIONS["build_exe"],
            "bdist_msi": WINDOWS_OPTIONS["bdist_msi"],
        },
        executables=[executable],
    )

if __name__ == "__main__":
    main()
