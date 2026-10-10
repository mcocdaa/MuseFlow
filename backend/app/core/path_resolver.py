import os
import socket
import sys
import time
from pathlib import Path
from typing import Tuple

# Configurable NAS & Mount Settings via Environment Variables
MUSEFLOW_NAS_HOST = os.getenv("MUSEFLOW_NAS_HOST", "")
MUSEFLOW_NAS_PORT = int(os.getenv("MUSEFLOW_NAS_PORT", "445"))
MUSEFLOW_NAS_MOUNT = os.getenv("MUSEFLOW_NAS_MOUNT", "/mnt/z")
MUSEFLOW_NAS_SHARE = os.getenv("MUSEFLOW_NAS_SHARE", "")

def resolve_physical_path(path_input: str | Path) -> Path:
    """
    Transparent cross-platform path resolution between Windows UNC / Drive Letters
    and Linux / WSL DrvFs mounts.
    
    Handles:
    - \\\\server\\share\\... <--> /mnt/z/...
    - Z:\\... <--> /mnt/z/...
    - D:\\... <--> /mnt/d/...
    - C:\\... <--> /mnt/c/...
    """
    if not path_input:
        return Path("")
    
    raw = str(path_input).strip()
    norm = raw.replace("\\", "/")
    is_windows = (sys.platform == "win32") or (os.name == "nt")
    
    if is_windows:
        # Linux DrvFs to Windows drive or UNC
        if norm.startswith("/mnt/z/"):
            return Path("Z:/" + norm[7:])
        elif norm.startswith("/mnt/d/"):
            return Path("D:/" + norm[7:])
        elif norm.startswith("/mnt/c/"):
            return Path("C:/" + norm[7:])
        return Path(raw)
    else:
        # Linux / WSL mode
        # 1. UNC share resolution (//host/share/subpath -> /mnt/z/subpath)
        if norm.startswith("//"):
            parts = norm[2:].split("/", 2)
            if len(parts) >= 3:
                sub = parts[2]
                return Path(MUSEFLOW_NAS_MOUNT) / sub
            
        # 2. Windows drive letters to /mnt/x
        if len(norm) >= 2 and norm[1] == ":":
            drive = norm[0].lower()
            rest = norm[2:].lstrip("/")
            return Path(f"/mnt/{drive}") / rest
            
        return Path(raw)

def is_network_or_nas_path(path_input: str | Path) -> bool:
    """Returns True if the path originates from a NAS mount or network share"""
    p_str = str(path_input).replace("\\", "/").lower()
    mount_lower = MUSEFLOW_NAS_MOUNT.lower()
    return (
        p_str.startswith(mount_lower)
        or p_str.startswith("z:")
        or (bool(MUSEFLOW_NAS_HOST) and MUSEFLOW_NAS_HOST.lower() in p_str)
    )

_nas_reachability_cache = {"online": None, "checked_at": 0.0}

def is_nas_online(timeout: float = 0.25) -> bool:
    """
    Rapid non-blocking check to determine if the network storage/mount is responsive.
    Caches result for 2.0s to avoid high-frequency socket probes or syscall blocks.
    """
    global _nas_reachability_cache
    now = time.time()
    if _nas_reachability_cache["online"] is not None and (now - _nas_reachability_cache["checked_at"] < 2.0):
        return _nas_reachability_cache["online"]

    online = False
    if MUSEFLOW_NAS_HOST:
        try:
            with socket.create_connection((MUSEFLOW_NAS_HOST, MUSEFLOW_NAS_PORT), timeout=timeout):
                online = True
        except Exception:
            online = False
    else:
        # Generic local mount directory responsiveness check
        mount_p = Path(MUSEFLOW_NAS_MOUNT)
        try:
            online = mount_p.exists() and mount_p.is_dir()
        except (OSError, IOError, TimeoutError):
            online = False

    _nas_reachability_cache["online"] = online
    _nas_reachability_cache["checked_at"] = now
    return online

def safe_path_exists(path: Path | str) -> bool:
    """
    Checks if a path exists, bypassing filesystem syscalls if the path is on a disconnected NAS.
    Prevents Linux kernel CIFS D-state sleep/deadlocks.
    """
    p = Path(path) if isinstance(path, str) else path
    if is_network_or_nas_path(p):
        if not is_nas_online():
            return False
    try:
        return p.exists()
    except (OSError, IOError, TimeoutError):
        return False

def safe_is_dir(path: Path | str) -> bool:
    """Safely checks if a path is a directory without hanging on offline network storage."""
    p = Path(path) if isinstance(path, str) else path
    if is_network_or_nas_path(p):
        if not is_nas_online():
            return False
    try:
        return p.is_dir()
    except (OSError, IOError, TimeoutError):
        return False

def test_file_readability(path: Path) -> Tuple[bool, str]:
    """
    Safely tests if a file is readable, handling network dropouts gracefully.
    """
    if is_network_or_nas_path(path) and not is_nas_online():
        return False, "nas_offline"
    try:
        if not path.exists():
            return False, "not_found"
        with open(path, "rb") as f:
            _ = f.read(1)
        return True, "ok"
    except (OSError, IOError, TimeoutError) as e:
        return False, f"io_error: {e}"
    except Exception as e:
        return False, f"error: {e}"
