"""
MuseFlow Library Auto-Watcher (后台自动同步与热感知守护进程)
定期检查外部存储挂载状态，并在发现有新文件或删除时自动增量同步，
让用户无需手动触发即可自动加载媒体库的最新变更。
"""

import time
import threading
import logging
from app.core.db import engine
from sqlmodel import Session
from app.services.sync_engine import sync_library_changes, check_mount_status

logger = logging.getLogger("museflow.watcher")

_watcher_thread: threading.Thread | None = None
_stop_event = threading.Event()

def _watcher_loop(interval_seconds: int = 600):
    logger.info(f"Library Auto-Watcher started (interval: {interval_seconds}s)")
    # 若数据库为空（如全新 Docker 容器首次启动挂载 /media），仅等待 3 秒即自动执行首次扫描建库；否则等待 60 秒
    initial_delay = 60
    try:
        from sqlmodel import select, func
        from app.models.entities import AssetUnit
        with Session(engine) as session:
            if session.exec(select(func.count(AssetUnit.id))).one() == 0:
                initial_delay = 3
    except Exception:
        pass

    if _stop_event.wait(initial_delay):
        return

    while not _stop_event.is_set():
        try:
            status = check_mount_status()
            if status.get("is_mounted") and status.get("valid_roots"):
                logger.info("Auto-Watcher: NAS is mounted. Performing incremental sync check...")
                with Session(engine) as session:
                    res = sync_library_changes(session, prune_missing=True)
                    if res.get("status") == "success":
                        added = res.get("added_units", 0)
                        pruned = res.get("pruned_units", 0)
                        if added > 0 or pruned > 0:
                            logger.info(f"Auto-Watcher: Detected changes! +{added} units, -{pruned} units")
            else:
                logger.debug("Auto-Watcher: NAS is not mounted or empty, skipping sync.")
        except Exception as e:
            logger.warning(f"Auto-Watcher background error: {e}")

        # Sleep interval
        if _stop_event.wait(interval_seconds):
            break

def start_library_watcher(interval_seconds: int = 600):
    global _watcher_thread, _stop_event
    if _watcher_thread and _watcher_thread.is_alive():
        return
    _stop_event.clear()
    _watcher_thread = threading.Thread(target=_watcher_loop, args=(interval_seconds,), daemon=True)
    _watcher_thread.start()

def stop_library_watcher():
    global _stop_event
    _stop_event.set()
