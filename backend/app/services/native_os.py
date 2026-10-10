import os
import platform
import subprocess
from pathlib import Path
from typing import Optional

def _is_wsl() -> bool:
    """判断当前运行环境是否为 WSL (Windows Subsystem for Linux)"""
    if platform.system() != "Linux":
        return False
    try:
        with open("/proc/version", "r") as f:
            return "microsoft" in f.read().lower()
    except Exception:
        return False

def _to_windows_path(path_obj: Path) -> Optional[str]:
    """通过 wslpath 将 Linux 路径转换为 Windows 宿主机路径"""
    try:
        res = subprocess.check_output(
            ["wslpath", "-w", str(path_obj)],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return res.strip()
    except Exception:
        return None

def open_in_file_explorer(target_path: str) -> bool:
    """在操作系统的文件管理器中定位并选中该文件/打开该文件夹"""
    path_obj = Path(target_path).resolve()
    if not path_obj.exists():
        return False

    system_name = platform.system()
    try:
        if _is_wsl():
            win_path = _to_windows_path(path_obj)
            if not win_path:
                return False
            explorer_bin = "/mnt/c/Windows/explorer.exe" if Path("/mnt/c/Windows/explorer.exe").exists() else "explorer.exe"
            args = [explorer_bin, f"/select,{win_path}"] if path_obj.is_file() else [explorer_bin, win_path]
            subprocess.Popen(
                args,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return True

        elif system_name == "Windows":
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
        else: # Standard Linux
            parent_dir = str(path_obj.parent) if path_obj.is_file() else str(path_obj)
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
        if _is_wsl():
            win_path = _to_windows_path(path_obj)
            if not win_path:
                return False
            explorer_bin = "/mnt/c/Windows/explorer.exe" if Path("/mnt/c/Windows/explorer.exe").exists() else "explorer.exe"
            # Passing file path to explorer.exe opens it using Windows file association (e.g. PotPlayer / VLC)
            subprocess.Popen(
                [explorer_bin, win_path],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return True

        elif system_name == "Windows":
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
