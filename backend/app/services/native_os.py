import os
import platform
import subprocess
from pathlib import Path

def open_in_file_explorer(target_path: str) -> bool:
    """在操作系统的文件管理器中定位并选中该文件/打开该文件夹"""
    path_obj = Path(target_path).resolve()
    if not path_obj.exists():
        return False

    system_name = platform.system()
    try:
        if system_name == "Windows":
            if path_obj.is_file():
                subprocess.Popen(["explorer.exe", f"/select,{str(path_obj)}"])
            else:
                subprocess.Popen(["explorer.exe", str(path_obj)])
            return True
        elif system_name == "Darwin": # macOS
            if path_obj.is_file():
                subprocess.Popen(["open", "-R", str(path_obj)])
            else:
                subprocess.Popen(["open", str(path_obj)])
            return True
        else: # Linux
            parent_dir = str(path_obj.parent) if path_obj.is_file() else str(path_obj)
            # Try dbus or file managers first, fallback to xdg-open
            try:
                subprocess.Popen(["xdg-open", parent_dir])
            except Exception:
                subprocess.Popen(["nautilus", parent_dir])
            return True
    except Exception as e:
        print(f"Error opening in explorer: {e}")
        return False

def open_with_default_app(target_path: str) -> bool:
    """使用操作系统默认关联程序打开文件"""
    path_obj = Path(target_path).resolve()
    if not path_obj.exists():
        return False

    system_name = platform.system()
    try:
        if system_name == "Windows":
            os.startfile(str(path_obj))
            return True
        elif system_name == "Darwin":
            subprocess.Popen(["open", str(path_obj)])
            return True
        else:
            subprocess.Popen(["xdg-open", str(path_obj)])
            return True
    except Exception as e:
        print(f"Error opening with default app: {e}")
        return False
