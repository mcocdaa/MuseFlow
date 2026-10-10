import json
import logging
import os
import re
import shutil
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import uuid

import httpx
from sqlmodel import Session, select

from app.core.config import (
    ALL_MEDIA_EXTS,
    SUPPORTED_AUDIO_EXTS,
    SUPPORTED_IMAGE_EXTS,
    SUPPORTED_VIDEO_EXTS,
    SUPPORTED_SUBTITLE_EXTS,
    DATA_DIR,
)
from app.core.path_resolver import resolve_physical_path, is_nas_online, is_network_or_nas_path
from app.models.entities import (
    AssetFile,
    AssetUnit,
    Collection,
    MaintenanceLeaseLock,
    ProjectionJournal,
)
from app.services.asmr_importer import (
    COVER_CACHE_DIR,
    RJ_PATTERN,
    extract_rj_code,
    fetch_and_cache_asmr_meta,
)

logger = logging.getLogger("museflow.physical_organizer")


def get_active_maintenance_locks() -> List[Dict[str, Any]]:
    """返回所有当前处于物理整理维护中的文件夹及租约信息 (落库防死锁)"""
    from app.core.db import engine
    now = datetime.now(timezone.utc)
    try:
        with Session(engine) as session:
            locks = session.exec(
                select(MaintenanceLeaseLock).where(MaintenanceLeaseLock.expires_at > now)
            ).all()
            return [
                {
                    "folder_path": l.folder_path,
                    "reason": l.reason,
                    "owner_token": l.owner_token,
                    "locked_at": l.locked_at.isoformat(),
                    "expires_at": l.expires_at.isoformat(),
                }
                for l in locks
            ]
    except Exception as e:
        logger.warning(f"Failed to query maintenance locks: {e}")
        return []


def acquire_maintenance_lock(
    folder_path: str, reason: str, owner_token: str = "triage", lease_seconds: int = 600
) -> bool:
    """获取某个物理目录的持久化租约锁 (默认 10 分钟自动超时，防崩溃僵尸锁)"""
    from app.core.db import engine
    p_str = str(resolve_physical_path(folder_path))
    now = datetime.now(timezone.utc)
    try:
        with Session(engine) as session:
            # 清理历史已过期的死锁
            expired = session.exec(
                select(MaintenanceLeaseLock).where(MaintenanceLeaseLock.expires_at < now)
            ).all()
            for exp in expired:
                session.delete(exp)

            existing = session.get(MaintenanceLeaseLock, p_str)
            if existing and existing.expires_at > now and existing.owner_token != owner_token:
                return False

            lock = MaintenanceLeaseLock(
                folder_path=p_str,
                reason=reason,
                owner_token=owner_token,
                locked_at=now,
                expires_at=now + timedelta(seconds=lease_seconds),
            )
            session.merge(lock)
            session.commit()
            return True
    except Exception as e:
        logger.error(f"Failed to acquire lease lock for {p_str}: {e}")
        return False


def release_maintenance_lock(folder_path: str, owner_token: Optional[str] = None) -> None:
    """释放某个物理目录的维护租约锁"""
    from app.core.db import engine
    p_str = str(resolve_physical_path(folder_path))
    try:
        with Session(engine) as session:
            lock = session.get(MaintenanceLeaseLock, p_str)
            if lock:
                if owner_token is None or lock.owner_token == owner_token:
                    session.delete(lock)
                    session.commit()
    except Exception as e:
        logger.warning(f"Failed to release maintenance lock for {p_str}: {e}")


def is_folder_in_maintenance(folder_path: str) -> Optional[Dict[str, Any]]:
    """检查某个路径（或其父目录）是否正处于维护整理中"""
    p_str = str(resolve_physical_path(folder_path))
    active_locks = get_active_maintenance_locks()
    for info in active_locks:
        locked_path = info["folder_path"]
        if (
            p_str == locked_path
            or p_str.startswith(locked_path.rstrip("/\\") + "/")
            or p_str.startswith(locked_path.rstrip("/\\") + "\\")
        ):
            return info
    return None


class PhysicalActionItem:
    def __init__(
        self,
        action_type: str, # "rename_dir", "move_dir", "set_mtime", "move_file", "create_dir"
        src_path: str,
        dst_path: Optional[str] = None,
        mtime_timestamp: Optional[float] = None,
        mtime_iso: Optional[str] = None,
        description: str = "",
        collection_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.action_type = action_type
        self.src_path = src_path
        self.dst_path = dst_path
        self.mtime_timestamp = mtime_timestamp
        self.mtime_iso = mtime_iso
        self.description = description
        self.collection_id = collection_id
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_type": self.action_type,
            "src_path": self.src_path,
            "dst_path": self.dst_path,
            "mtime_timestamp": self.mtime_timestamp,
            "mtime_iso": self.mtime_iso,
            "description": self.description,
            "collection_id": self.collection_id,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PhysicalActionItem":
        return cls(
            action_type=data["action_type"],
            src_path=data["src_path"],
            dst_path=data.get("dst_path"),
            mtime_timestamp=data.get("mtime_timestamp"),
            mtime_iso=data.get("mtime_iso"),
            description=data.get("description", ""),
            collection_id=data.get("collection_id"),
            metadata=data.get("metadata", {}),
        )


class PhysicalTriagePlan:
    def __init__(
        self,
        target_folder: str,
        rule_name: str,
        summary: str,
        actions: List[PhysicalActionItem],
        plan_id: Optional[str] = None,
    ):
        self.plan_id = plan_id or str(uuid.uuid4())
        self.target_folder = target_folder
        self.rule_name = rule_name
        self.summary = summary
        self.actions = actions
        self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "target_folder": self.target_folder,
            "rule_name": self.rule_name,
            "summary": self.summary,
            "created_at": self.created_at,
            "total_actions": len(self.actions),
            "actions": [a.to_dict() for a in self.actions],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PhysicalTriagePlan":
        actions = [PhysicalActionItem.from_dict(a) for a in data.get("actions", [])]
        plan = cls(
            target_folder=data["target_folder"],
            rule_name=data.get("rule_name", "custom"),
            summary=data.get("summary", ""),
            actions=actions,
            plan_id=data.get("plan_id"),
        )
        plan.created_at = data.get("created_at", datetime.now(timezone.utc).isoformat())
        return plan


def _is_chinese_folder(entry: Path, title: str) -> bool:
    name_check = f"{entry.name} {title}"
    chinese_keywords = ["中文", "中国語", "漢化", "汉化", "简中", "繁中", "翻译", "字幕", "台本", "中字", "精翻"]
    if any(k in name_check for k in chinese_keywords):
        return True

    # 中文特有高频语法词与结构词
    common_cn_words = ["的", "了", "在", "是", "我", "和", "跟", "与", "與", "你", "选择", "選擇", "做", "这", "這", "说", "說", "有", "很", "篇", "第", "章", "女友", "朋友", "大姐姐"]
    if any(w in entry.name for w in common_cn_words):
        return True

    # 统计假名与汉字比例：若有较多汉字且无任何日文假名（平假名/片假名），则判定为中文
    kana_count = len(re.findall(r'[\u3040-\u309F\u30A0-\u30FF]', entry.name))
    hanzi_count = len(re.findall(r'[\u4E00-\u9FFF]', entry.name))
    if hanzi_count >= 4 and kana_count == 0:
        return True

    try:
        for p in entry.iterdir():
            if any(k in p.name for k in chinese_keywords):
                return True
            if p.is_file() and p.suffix.lower() in (".lrc", ".srt", ".vtt"):
                return True
            if p.is_dir():
                try:
                    for sub in p.iterdir():
                        if any(k in sub.name for k in chinese_keywords):
                            return True
                        if sub.is_file() and sub.suffix.lower() in (".lrc", ".srt", ".vtt"):
                            return True
                except Exception:
                    pass
    except Exception:
        pass
    return False


def inspect_directory_assets(session: Session, target_folder_str: str) -> Dict[str, Any]:
    """
    深度探查指定作用域文件夹内的资产情况：
    - 统计总大小、文件数、子文件夹数
    - 识别所有 RJ 作品及其官方发售日期、汉化状态、CV、社团
    - 识别散落图片/音视频
    - 关联已入库的 Collection 和 AssetUnit
    """
    target_path = resolve_physical_path(target_folder_str)
    if not target_path.exists() or not target_path.is_dir():
        return {"error": f"Target folder does not exist or is not a directory: {target_folder_str}"}

    rj_candidates: List[Tuple[Path, str]] = []
    loose_images: List[str] = []
    loose_audios: List[str] = []
    loose_videos: List[str] = []
    subdirectories: List[str] = []

    for entry in sorted(target_path.iterdir()):
        if entry.is_dir():
            subdirectories.append(entry.name)
            rj = extract_rj_code(entry.name)
            if rj:
                rj_candidates.append((entry, rj))
        elif entry.is_file():
            ext = entry.suffix.lower()
            if ext in SUPPORTED_IMAGE_EXTS:
                loose_images.append(entry.name)
            elif ext in SUPPORTED_AUDIO_EXTS:
                loose_audios.append(entry.name)
            elif ext in SUPPORTED_VIDEO_EXTS:
                loose_videos.append(entry.name)

    def _fetch_meta(item: Tuple[Path, str]):
        entry, rj = item
        meta = fetch_and_cache_asmr_meta(rj, download_cover=False)
        return entry, rj, meta

    rj_results = []
    if rj_candidates:
        with ThreadPoolExecutor(max_workers=min(8, len(rj_candidates))) as executor:
            rj_results = list(executor.map(_fetch_meta, rj_candidates))

    rj_works: List[Dict[str, Any]] = []
    for entry, rj, meta in rj_results:
        col = session.exec(select(Collection).where(Collection.folder_path == str(entry))).first()
        title = meta.get("title") if meta else entry.name
        is_chinese = _is_chinese_folder(entry, title)
        release_date = meta.get("release") or meta.get("regist_date") if meta else None

        stat = entry.stat()
        current_mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()

        rj_works.append({
            "folder_name": entry.name,
            "folder_path": str(entry),
            "rj_code": rj,
            "title": title,
            "circle": meta.get("circle") if meta else "",
            "vas": meta.get("vas", []) if meta else [],
            "is_chinese": is_chinese,
            "release_date": release_date,
            "current_mtime": current_mtime,
            "collection_id": col.id if col else None,
        })

    return {
        "status": "success",
        "target_folder": str(target_path),
        "total_subdirectories": len(subdirectories),
        "total_rj_works": len(rj_works),
        "rj_works": rj_works,
        "loose_images": loose_images,
        "loose_audios": loose_audios,
        "loose_videos": loose_videos,
    }


def plan_rj_normalization_and_dates(
    session: Session,
    target_folder_str: str,
    rename_template: str = "[{rj_code}] {title}",
    update_mtime_to_release: bool = True,
) -> PhysicalTriagePlan:
    """
    方案生成器 1：RJ 文件夹标准化与发售日期对齐
    - 规范化重命名为例如：[RJ123456] 甜蜜耳语与日常陪伴
    - 修改文件夹 mtime 为作品在 DLsite 官方发布的时间
    - 绑定数据库 Collection 和 AssetFile 路径自愈
    """
    inspection = inspect_directory_assets(session, target_folder_str)
    if "error" in inspection:
        raise ValueError(inspection["error"])

    target_path = resolve_physical_path(target_folder_str)
    actions: List[PhysicalActionItem] = []

    for work in inspection.get("rj_works", []):
        old_folder = Path(work["folder_path"])
        rj_code = work["rj_code"]
        title = work["title"] or old_folder.name
        # 清理非法字符用于文件夹命名
        clean_title = re.sub(r'[\\/*?:"<>|]', "", title).strip()
        # 去除 title 中前缀的 RJ 码，避免格式化后出现 [RJxxxxxx] RJxxxxxx 或 [RJxxxxxx] [RJxxxxxx]
        clean_title = re.sub(r'^\[?' + re.escape(rj_code) + r'\]?\s*[-_]?\s*', '', clean_title, flags=re.I).strip()
        if len(clean_title) > 160:
            clean_title = clean_title[:160].strip()
        if not clean_title:
            clean_title = rj_code
        new_folder_name = rename_template.format(rj_code=rj_code, title=clean_title)
        new_folder = target_path / new_folder_name

        col_id = work.get("collection_id")

        # 1. 重命名动作 (若名字不同)
        if old_folder.name != new_folder_name and not new_folder.exists():
            actions.append(
                PhysicalActionItem(
                    action_type="rename_dir",
                    src_path=str(old_folder),
                    dst_path=str(new_folder),
                    description=f"标准化重命名：{old_folder.name} -> {new_folder_name}",
                    collection_id=col_id,
                    metadata={"rj_code": rj_code, "new_title": clean_title},
                )
            )
            folder_for_time = new_folder
        else:
            folder_for_time = old_folder

        # 2. 对齐发布时间动作
        rel_date_str = work.get("release_date")
        if update_mtime_to_release and rel_date_str:
            try:
                # 支持 2022-05-18 或 2022-05-18 00:00:00
                if " " in rel_date_str:
                    dt = datetime.strptime(rel_date_str.split(".")[0], "%Y-%m-%d %H:%M:%S")
                else:
                    dt = datetime.strptime(rel_date_str[:10], "%Y-%m-%d")
                dt = dt.replace(tzinfo=timezone.utc)
                ts = dt.timestamp()

                actions.append(
                    PhysicalActionItem(
                        action_type="set_mtime",
                        src_path=str(folder_for_time),
                        dst_path=str(folder_for_time),
                        mtime_timestamp=ts,
                        mtime_iso=dt.isoformat(),
                        description=f"修改文件夹时间为官方发售日期：{dt.strftime('%Y-%m-%d')}",
                        collection_id=col_id,
                        metadata={"release_date": rel_date_str},
                    )
                )
            except Exception as e:
                logger.warning(f"Failed to parse release date {rel_date_str}: {e}")

    summary = (
        f"在作用域「{target_path.name}」内对 {len(inspection.get('rj_works', []))} 个 RJ 作品执行物理整理："
        f"共计规划 {len([a for a in actions if a.action_type == 'rename_dir'])} 项目录规范重命名，"
        f"以及 {len([a for a in actions if a.action_type == 'set_mtime'])} 项发售时间对齐。"
    )

    return PhysicalTriagePlan(
        target_folder=str(target_path),
        rule_name="rj_normalization_and_dates",
        summary=summary,
        actions=actions,
    )


def plan_rj_separate_untranslated(
    session: Session,
    target_folder_str: str,
    untranslated_subfolder_name: str = "待翻译",
) -> PhysicalTriagePlan:
    """
    方案生成器 2：未汉化作品隔离归流
    - 检查 target_folder 下所有的 RJ 作品
    - 将没有中文字幕/中文汉化的作品物理移动至 {target_folder}/{untranslated_subfolder_name}/
    - 排除已经在未汉化子目录中的作品
    """
    inspection = inspect_directory_assets(session, target_folder_str)
    if "error" in inspection:
        raise ValueError(inspection["error"])

    target_path = resolve_physical_path(target_folder_str)
    dest_dir = target_path / untranslated_subfolder_name

    actions: List[PhysicalActionItem] = []

    # 确保目标文件夹创建
    if not dest_dir.exists():
        actions.append(
            PhysicalActionItem(
                action_type="create_dir",
                src_path=str(dest_dir),
                dst_path=str(dest_dir),
                description=f"创建待翻译专用目录：{untranslated_subfolder_name}",
            )
        )

    for work in inspection.get("rj_works", []):
        old_folder = Path(work["folder_path"])
        # 若已经在待翻译目录下，跳过
        if old_folder.parent == dest_dir or old_folder == dest_dir:
            continue

        if not work.get("is_chinese", False):
            new_folder = dest_dir / old_folder.name
            actions.append(
                PhysicalActionItem(
                    action_type="move_dir",
                    src_path=str(old_folder),
                    dst_path=str(new_folder),
                    description=f"将未汉化作品移入待翻译归类：{old_folder.name} -> {untranslated_subfolder_name}/",
                    collection_id=work.get("collection_id"),
                    metadata={"rj_code": work.get("rj_code"), "title": work.get("title")},
                )
            )

    summary = (
        f"在作用域「{target_path.name}」内筛选未汉化音声：发现 {len(actions)} 项操作，"
        f"拟将未翻译作品归入「{untranslated_subfolder_name}/」子目录以待后续精翻。"
    )

    return PhysicalTriagePlan(
        target_folder=str(target_path),
        rule_name="rj_separate_untranslated",
        summary=summary,
        actions=actions,
    )


def plan_interactive_topology(
    session: Session,
    target_folder_str: str,
    topology_mapping: Dict[str, List[str]], # {"壁纸/原神": ["*.png", "genshin_*"], ...}
    summary: str = "自定义智能拓扑结构归类",
) -> PhysicalTriagePlan:
    """
    方案生成器 3：与 Agent 讨论定制的任意目录拓扑
    - 接收用户与 Agent 商讨确定的文件夹结构映射
    - 将目标目录下的散落文件移动至规划子目录
    """
    target_path = resolve_physical_path(target_folder_str)
    if not target_path.exists() or not target_path.is_dir():
        raise ValueError(f"Target folder does not exist: {target_folder_str}")

    actions: List[PhysicalActionItem] = []

    for sub_rel_path, patterns in topology_mapping.items():
        sub_dir = target_path / sub_rel_path
        if not sub_dir.exists():
            actions.append(
                PhysicalActionItem(
                    action_type="create_dir",
                    src_path=str(sub_dir),
                    dst_path=str(sub_dir),
                    description=f"创建目标拓扑目录：{sub_rel_path}",
                )
            )

        matched_files = set()
        for p in patterns:
            for f in target_path.glob(p):
                if f.is_file() and f.parent == target_path: # 只针对当前散落顶层的文件
                    matched_files.add(f)

        for mf in sorted(matched_files):
            dst_file = sub_dir / mf.name
            actions.append(
                PhysicalActionItem(
                    action_type="move_file",
                    src_path=str(mf),
                    dst_path=str(dst_file),
                    description=f"归档散落文件：{mf.name} -> {sub_rel_path}/",
                )
            )

    return PhysicalTriagePlan(
        target_folder=str(target_path),
        rule_name="custom_topology",
        summary=summary,
        actions=actions,
    )


def execute_triage_plan(
    session: Session,
    plan: PhysicalTriagePlan,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    执行物理重组方案：
    1. 激活受控维护锁，提示前端用户该目录作品正处在维护整理中；
    2. 执行物理磁盘操作 (目录创建、改名、搬移、utime 修改)；
    3. 同步原子自愈 SQLite 数据库索引 (Collection.folder_path, AssetFile.file_path)；
    4. 释放维护锁，返回执行报告。
    """
    target_folder = plan.target_folder
    
    if dry_run:
        return {
            "status": "dry_run",
            "message": "干跑预演完成，未修改任何物理文件与数据库",
            "plan": plan.to_dict(),
        }

    # 检查网络/NAS 存活状态
    if is_network_or_nas_path(target_folder) and not is_nas_online():
        raise RuntimeError("NAS 存储网络当前离线，拒绝执行物理搬迁，防止数据损坏")

    # 1. 挂上持久化租约锁 (默认 10 分钟自动超时防死锁)
    if not acquire_maintenance_lock(target_folder, plan.summary, owner_token=plan.plan_id):
        raise RuntimeError(f"目标目录已处于维护锁定期，拒绝重入操作: {target_folder}")

    executed_count = 0
    errors: List[str] = []

    try:
        # 步骤 1：批量记录 PENDING 意图日志 (两阶段日志预写)
        journals: List[Tuple[ProjectionJournal, PhysicalActionItem]] = []
        for action in plan.actions:
            j = ProjectionJournal(
                plan_id=plan.plan_id,
                action_type=action.action_type,
                src_path=action.src_path,
                dst_path=action.dst_path,
                status="PENDING",
            )
            session.add(j)
            journals.append((j, action))
        session.commit()

        # 步骤 2：在 DB 事务外部执行物理磁盘操作 (绝不在长事务内持有 SQLite 锁)
        path_mapping_updates: List[Tuple[str, str, str, Optional[str]]] = []  # (type, src, dst, new_title)

        for journal_entry, action in journals:
            try:
                if action.action_type == "create_dir":
                    p = Path(action.src_path)
                    p.mkdir(parents=True, exist_ok=True)
                    journal_entry.status = "EXECUTED"
                    executed_count += 1

                elif action.action_type in ("rename_dir", "move_dir"):
                    src = Path(action.src_path)
                    dst = Path(action.dst_path) if action.dst_path else None
                    if not src.exists() or not dst:
                        continue
                    dst.parent.mkdir(parents=True, exist_ok=True)

                    # 物理位移 (安全处理跨卷与同卷)
                    src_str = str(src.resolve())
                    dst_str = str(dst.resolve()) if dst.exists() else str(dst)

                    shutil.move(str(src), str(dst))

                    path_mapping_updates.append(
                        ("dir", src_str, str(dst.resolve()), action.metadata.get("new_title"))
                    )
                    journal_entry.status = "EXECUTED"
                    executed_count += 1

                elif action.action_type == "move_file":
                    src = Path(action.src_path)
                    dst = Path(action.dst_path) if action.dst_path else None
                    if not src.exists() or not dst:
                        continue
                    dst.parent.mkdir(parents=True, exist_ok=True)

                    src_str = str(src.resolve())
                    dst_str = str(dst)

                    shutil.move(str(src), str(dst))

                    path_mapping_updates.append(
                        ("file", src_str, str(dst.resolve()), None)
                    )
                    journal_entry.status = "EXECUTED"
                    executed_count += 1

                elif action.action_type == "set_mtime":
                    target = Path(action.src_path)
                    ts = action.mtime_timestamp
                    if target.exists() and ts:
                        try:
                            os.utime(str(target), (ts, ts))
                            journal_entry.status = "EXECUTED"
                            executed_count += 1
                        except PermissionError:
                            logger.warning(
                                f"PermissionError: cannot update mtime on {target}. "
                                "DrvFs mount requires '-o uid=1000' for non-root utime."
                            )

            except Exception as e:
                err_msg = f"Failed action {action.action_type} for {action.src_path}: {e}"
                logger.error(err_msg)
                errors.append(err_msg)
                journal_entry.status = "FAILED"
                journal_entry.error_message = str(e)
                # 物理出错时中止后续搬迁
                break

        # 步骤 3：单次短事务批量原子自愈数据库 (毫秒级短事务，绝不产生锁死)
        try:
            for item_type, src_s, dst_s, new_title in path_mapping_updates:
                if item_type == "dir":
                    cols = session.exec(select(Collection).where(Collection.folder_path == src_s)).all()
                    for c in cols:
                        c.folder_path = dst_s
                        if new_title:
                            c.name = new_title
                        session.add(c)

                    files = session.exec(select(AssetFile).where(AssetFile.file_path.startswith(src_s))).all()
                    for f in files:
                        f.file_path = f.file_path.replace(src_s, dst_s, 1)
                        session.add(f)

                elif item_type == "file":
                    f_rec = session.exec(select(AssetFile).where(AssetFile.file_path == src_s)).first()
                    if f_rec:
                        f_rec.file_path = dst_s
                        f_rec.file_name = Path(dst_s).name
                        session.add(f_rec)

            for j, _ in journals:
                if j.status == "EXECUTED":
                    j.status = "COMMITTED"
                session.add(j)

            session.commit()
        except Exception as db_err:
            session.rollback()
            err_msg = f"Database batch path reconciliation failed: {db_err}"
            logger.critical(err_msg)
            errors.append(err_msg)

    finally:
        # 释放持久化租约锁
        release_maintenance_lock(target_folder, owner_token=plan.plan_id)

    return {
        "status": "success" if not errors else "partial_success",
        "plan_id": plan.plan_id,
        "target_folder": target_folder,
        "total_actions": len(plan.actions),
        "executed_count": executed_count,
        "errors": errors,
    }
