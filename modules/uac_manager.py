"""
UAC权限提升模块
Windows管理员权限管理
"""
import sys
import ctypes
from typing import Optional


def is_admin() -> bool:
    """检查是否以管理员权限运行"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def run_as_admin() -> bool:
    """
    尝试以管理员权限重新运行程序

    Returns:
        如果成功提升则返回True（原进程应退出）
        失败返回False
    """
    if sys.platform != "win32":
        return False

    try:
        # 使用ShellExecute以管理员权限重新运行程序
        params = " ".join([f'"{arg}"' for arg in sys.argv])
        hinstance = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, params, None, 1
        )
        # 如果返回值大于32表示成功
        return hinstance > 32
    except Exception as e:
        print(f"[UAC] 权限提升失败: {e}")
        return False


def ensure_admin():
    """
    确保程序以管理员权限运行。
    cx_Freeze 使用 uac_admin=True 配置后，打包程序会自动请求UAC提权。
    """
    # 检查是否为打包环境
    is_packaged = getattr(sys, 'frozen', False)
    
    if is_packaged:
        if not is_admin():
            # cx_Freeze 已经通过 app.manifest/uac_admin=True 处理了 UAC 请求
            # 如果没有权限，通常表示用户拒绝了UAC
            print("[UAC] 需要管理员权限才能运行本程序")
            # 显示错误提示（使用 ctypes，不依赖 PyQt）
            try:
                ctypes.windll.user32.MessageBoxW(
                    0,
                    "需要管理员权限才能运行本程序，请以管理员身份运行。",
                    "权限不足",
                    0x10 | 0x0  # MB_ICONERROR | MB_OK
                )
            except:
                pass
            sys.exit(1)
        else:
            print("[UAC] 已获得管理员权限")
    else:
        print("[UAC] 开发环境，跳过 UAC 权限检查")
