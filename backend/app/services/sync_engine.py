"""
MuseFlow Library Sync & Re-Index Engine (库数据同步与重构引擎)
支持：
1. 全量清空与重建 (Wipe & Re-index):
   - 清空 AssetFile, AssetUnit, Collection, SupersetUnitLink, AssetUnitTagLink, TelemetryLog
   - 保持 TagClass 与 Tag 本体词表定义完整
   - 全量非破坏性遍历扫描物理文件
   - 自动运行系列拓扑分卷归拢 (collection_rollup)
   - 自动批量反向多维打标 (reverse_tagger)
2. 增量热感知与变更同步 (Incremental Sync):
   - 扫描新入库的文件与作品
   - 校验已删除/移动的旧文件并级联裁剪孤儿单元 (Pruning)
   - 自动为新增作品执行反向打标
   - 输出清晰的变更差量 (Diff Summary)
"""

import os
import time
import threading
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from sqlmodel import Session, select, func

from app.models.entities import (
    AssetFile,
    AssetUnit,
    Collection,
    SupersetUnitLink,
    AssetUnitTagLink,
    LibraryRoot,
    TelemetryLog,
)
from app.core.config import MEDIA_SEARCH_ROOTS, MUSEFLOW_NAS_MOUNT
from app.services.scanner import scan_directory
from app.services.collection_rollup import rollup_split_work_collections
from app.services.reverse_tagger import batch_reverse_tag_all_units

logger = logging.getLogger("museflow.sync_engine")

DEFAULT_SEARCH_ROOTS = MEDIA_SEARCH_ROOTS

def attempt_auto_mount() -> bool:
    """尝试自动挂载 NAS/存储挂载点（利用 /etc/fstab 或免密挂载）"""
    mount_target = Path(MUSEFLOW_NAS_MOUNT)
    try:
        if mount_target.exists() and any(mount_target.iterdir()):
            return True
    except Exception:
        pass

    try:
        # 1. 若 fstab 中声明了 users 选项，普通用户可直接 mount
        res = os.system(f"mount {MUSEFLOW_NAS_MOUNT} 2>/dev/null")
        if res == 0:
            if mount_target.exists() and any(mount_target.iterdir()):
                logger.info(f"Successfully auto-mounted {MUSEFLOW_NAS_MOUNT} via user mount")
                return True
        # 2. 尝试 sudo -n mount
        res = os.system(f"sudo -n mount {MUSEFLOW_NAS_MOUNT} 2>/dev/null")
        if res == 0:
            if mount_target.exists() and any(mount_target.iterdir()):
                logger.info(f"Successfully auto-mounted {MUSEFLOW_NAS_MOUNT} via sudo -n mount")
                return True
        # 3. 尝试直接挂载其他候选配置路径
        for r in DEFAULT_SEARCH_ROOTS:
            rp = Path(r)
            if rp != mount_target and rp.exists():
                os.system(f"mount {r} 2>/dev/null || sudo -n mount {r} 2>/dev/null")
    except Exception as e:
        logger.debug(f"attempt_auto_mount failed: {e}")
    return False

def check_mount_status(auto_mount_if_needed: bool = True) -> Dict[str, Any]:
    """检查 NAS 与存储挂载状态（支持按需尝试自愈自动挂载）"""
    mount_target = Path(MUSEFLOW_NAS_MOUNT)
    is_mounted = False
    details = {}
    
    # 动态检测主挂载点及所有配置的检索根目录
    candidate_paths = [mount_target] + [Path(r) for r in DEFAULT_SEARCH_ROOTS]
    seen_paths = set()
    for cp in candidate_paths:
        str_cp = str(cp)
        if str_cp in seen_paths:
            continue
        seen_paths.add(str_cp)
        if cp.exists():
            try:
                entries = [p.name for p in cp.iterdir()][:15]
                if entries:
                    is_mounted = True
                    details["entries"] = entries
                    details["active_mount"] = str_cp
                    break
            except Exception as e:
                details["error"] = str(e)

    if not is_mounted and auto_mount_if_needed:
        if attempt_auto_mount():
            is_mounted = True
            try:
                details["entries"] = [p.name for p in mount_target.iterdir()][:15]
            except Exception:
                pass
            
    # Detect valid scanning roots
    valid_roots = []
    for r in DEFAULT_SEARCH_ROOTS:
        rp = Path(r)
        if rp.exists() and rp.is_dir():
            try:
                # Only consider non-empty directories as valid roots
                if any(rp.iterdir()):
                    valid_roots.append(str(rp))
            except Exception:
                pass
            
    return {
        "is_mounted": is_mounted,
        "mount_point": MUSEFLOW_NAS_MOUNT,
        "valid_roots": valid_roots,
        "details": details
    }

def wipe_media_database(session: Session) -> Dict[str, int]:
    """
    清空媒体数据（保留 TagClass、Tag 词表定义与用户配置），
    为全量全新采集做干净准备。
    """
    from sqlalchemy import text

    stats = {
        "deleted_tag_links": session.exec(select(func.count(AssetUnitTagLink.unit_id))).one(),
        "deleted_superset_links": session.exec(select(func.count(SupersetUnitLink.unit_id))).one(),
        "deleted_telemetry_logs": session.exec(select(func.count(TelemetryLog.id))).one(),
        "deleted_files": session.exec(select(func.count(AssetFile.id))).one(),
        "deleted_units": session.exec(select(func.count(AssetUnit.id))).one(),
        "deleted_collections": session.exec(select(func.count(Collection.id))).one(),
        "deleted_library_roots": session.exec(select(func.count(LibraryRoot.id))).one(),
    }

    # 解除自引用外键与循环指针约束
    session.execute(text("UPDATE collection SET parent_id = NULL, cover_asset_id = NULL"))
    session.execute(text("UPDATE assetunit SET collection_id = NULL, cover_file_id = NULL"))
    session.execute(text("UPDATE assetfile SET asset_unit_id = NULL"))
    session.flush()

    # 安全原子清理关联表与实体表
    session.execute(text("DELETE FROM asset_unit_tag_link"))
    session.execute(text("DELETE FROM supersetunitlink"))
    session.execute(text("DELETE FROM telemetrylog"))
    session.execute(text("DELETE FROM assetfile"))
    session.execute(text("DELETE FROM assetunit"))
    session.execute(text("DELETE FROM collection"))
    session.execute(text("DELETE FROM libraryroot"))
    session.commit()

    logger.info(f"Database media wiped cleanly: {stats}")
    return stats

_sync_lock = threading.Lock()

def _sync_library_changes_internal(
    session: Session,
    root_paths: Optional[List[str]] = None,
    prune_missing: bool = True
) -> Dict[str, Any]:
    """增量检测并同步物理 NAS 的新增、修改与删除变更（内部执行）"""
    start_t = time.time()
    
    # 1. Determine roots
    roots_to_scan = []
    if root_paths:
        roots_to_scan = [p for p in root_paths if Path(p).exists()]
    else:
        # Check existing LibraryRoot records first
        saved_roots = session.exec(select(LibraryRoot)).all()
        for sr in saved_roots:
            if Path(sr.path).exists():
                roots_to_scan.append(sr.path)
        if not roots_to_scan:
            for dr in DEFAULT_SEARCH_ROOTS:
                if Path(dr).exists():
                    roots_to_scan.append(dr)
                    break

    if not roots_to_scan:
        return {
            "status": "error",
            "message": f"未找到有效的物理媒体库目录，请确认存储挂载正常或在 .env 中配置 MUSEFLOW_MEDIA_ROOTS！",
            "mount_status": check_mount_status()
        }

    # 2. Prune missing records if requested
    pruned_files = 0
    pruned_units = 0
    pruned_cols = 0
    if prune_missing:
        # 按父目录聚合批量校验，避免在 SMB/NAS 上发起数千次单文件 stat RPC
        from collections import defaultdict
        all_files = session.exec(select(AssetFile)).all()
        files_by_parent = defaultdict(list)
        for f in all_files:
            files_by_parent[os.path.dirname(f.file_path)].append(f)

        for parent_dir, dir_files in files_by_parent.items():
            try:
                existing_names = set(os.listdir(parent_dir)) if os.path.isdir(parent_dir) else set()
            except OSError:
                existing_names = set()
            for f in dir_files:
                if os.path.basename(f.file_path) not in existing_names:
                    session.delete(f)
                    pruned_files += 1
        session.commit()
        
        # Check units without files
        all_units = session.exec(select(AssetUnit)).all()
        for u in all_units:
            count = session.exec(select(func.count(AssetFile.id)).where(AssetFile.asset_unit_id == u.id)).one()
            if count == 0:
                # Remove tag links, superset links, and telemetry logs
                tlinks = session.exec(select(AssetUnitTagLink).where(AssetUnitTagLink.unit_id == u.id)).all()
                for tl in tlinks:
                    session.delete(tl)
                slinks = session.exec(select(SupersetUnitLink).where(SupersetUnitLink.unit_id == u.id)).all()
                for sl in slinks:
                    session.delete(sl)
                tlogs = session.exec(select(TelemetryLog).where(TelemetryLog.unit_id == u.id)).all()
                for tl in tlogs:
                    session.delete(tl)
                # Clear any collection cover reference
                cols_with_cover = session.exec(select(Collection).where(Collection.cover_asset_id == u.id)).all()
                for col_c in cols_with_cover:
                    col_c.cover_asset_id = None
                    session.add(col_c)
                session.delete(u)
                pruned_units += 1
        session.commit()
        
        # Check collections whose physical folder no longer exists
        all_cols = session.exec(select(Collection)).all()
        # Sort leaf-first (deepest path first) to avoid foreign key parent_id conflicts
        cols_sorted = sorted(all_cols, key=lambda c: len(Path(c.folder_path).parts) if c.folder_path else 0, reverse=True)
        for c in cols_sorted:
            if c.folder_path and not os.path.exists(c.folder_path):
                unit_count = session.exec(select(func.count(AssetUnit.id)).where(AssetUnit.collection_id == c.id)).one()
                child_count = session.exec(select(func.count(Collection.id)).where(Collection.parent_id == c.id)).one()
                if unit_count == 0 and child_count == 0:
                    session.delete(c)
                    pruned_cols += 1
        session.commit()

    # 3. Incremental scan of roots
    total_new_units = 0
    total_new_files = 0
    for r in roots_to_scan:
        res = scan_directory(session, r)
        total_new_units += res.get("total_units", 0)
        total_new_files += res.get("total_files", 0)

    # 4. Rollup collection topology & group multipart series in buckets
    from app.services.collection_rollup import group_multipart_works_in_buckets
    from app.services.tag_organizer import reorganize_all_tags

    rollup_res = rollup_split_work_collections(session)
    group_res = group_multipart_works_in_buckets(session)

    # 5. Reverse tag newly added units and reorganize tag taxonomy
    tag_counts = {}
    if total_new_units > 0 or pruned_units > 0 or total_new_files > 0:
        tag_counts = batch_reverse_tag_all_units(session)
        reorganize_all_tags(session)

    elapsed = round(time.time() - start_t, 2)
    return {
        "status": "success",
        "roots_scanned": roots_to_scan,
        "added_units": total_new_units,
        "added_files": total_new_files,
        "pruned_files": pruned_files,
        "pruned_units": pruned_units,
        "pruned_collections": pruned_cols,
        "merged_collections": rollup_res.get("merged_collections_count", 0),
        "tag_counts": tag_counts,
        "elapsed_seconds": elapsed,
    }

def sync_library_changes(
    session: Session,
    root_paths: Optional[List[str]] = None,
    prune_missing: bool = True
) -> Dict[str, Any]:
    """增量检测并同步物理 NAS 的新增、修改与删除变更（带线程锁防护）"""
    if not _sync_lock.acquire(blocking=False):
        logger.info("Sync lock is busy. Skipping concurrent sync request.")
        return {
            "status": "busy",
            "message": "媒体库同步或重构正在进行中，请稍候...",
        }
    try:
        return _sync_library_changes_internal(session, root_paths=root_paths, prune_missing=prune_missing)
    finally:
        _sync_lock.release()

def wipe_and_rebuild_all(
    session: Session,
    root_paths: Optional[List[str]] = None
) -> Dict[str, Any]:
    """清空旧数据并重新全量扫描与打标构建（带线程锁防护）"""
    if not _sync_lock.acquire(blocking=False):
        logger.info("Sync lock is busy. Skipping concurrent wipe request.")
        return {
            "status": "busy",
            "message": "媒体库同步或重构正在进行中，请稍候...",
        }
    try:
        wipe_stats = wipe_media_database(session)
        sync_stats = _sync_library_changes_internal(session, root_paths=root_paths, prune_missing=False)
        sync_stats["wiped"] = wipe_stats
        return sync_stats
    finally:
        _sync_lock.release()
