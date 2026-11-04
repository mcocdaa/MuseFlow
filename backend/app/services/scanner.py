import os
import mimetypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from sqlmodel import Session, select
from app.core.config import ALL_MEDIA_EXTS
from app.models.entities import Collection, AssetUnit, AssetFile, LibraryRoot
from app.services.bundle_detector import analyze_folder_for_bundles
from app.services.media_processor import get_media_dimensions_and_duration
from app.services.collection_rollup import is_accessory_collection_name, WORK_CODE_REGEX, DISC_REGEX

def get_or_create_collection_hierarchy(session: Session, folder_path: Path, root_path: Path) -> Optional[Collection]:
    """根据文件夹路径创建或获取对应的系列 (Collection) 树形层级"""
    try:
        rel_path = folder_path.relative_to(root_path)
    except ValueError:
        return None

    if str(rel_path) == ".":
        # Root folder itself
        col = session.exec(select(Collection).where(Collection.folder_path == str(folder_path))).first()
        if not col:
            col = Collection(name=folder_path.name or "媒体库根目录", folder_path=str(folder_path))
            session.add(col)
            session.commit()
            session.refresh(col)
        return col

    # Traverse parts
    current_parent_id = None
    current_folder = root_path
    last_col = None
    for part in rel_path.parts:
        # 如果当前部分本身是带标准作品编号的文件夹，不再为其创建 Collection 包装层，而是直接归入上级分类/创作者集合！
        if WORK_CODE_REGEX.search(part):
            break

        # 过滤 Disc 1 / CD 1 及各类附件/花絮/图片目录
        if last_col is not None and (is_accessory_collection_name(part) or DISC_REGEX.search(part)):
            continue

        current_folder = current_folder / part
        col = session.exec(select(Collection).where(Collection.folder_path == str(current_folder))).first()
        if not col:
            col = Collection(
                name=part,
                folder_path=str(current_folder),
                parent_id=current_parent_id
            )
            session.add(col)
            session.commit()
            session.refresh(col)
        current_parent_id = col.id
        last_col = col

    return last_col


_NON_DIR_EXTS = ALL_MEDIA_EXTS | {
    ".ithmb", ".tif", ".tiff", ".psd", ".clip", ".sai", ".ai", ".eps", ".svg", ".ico",
    ".wma", ".opus", ".ts", ".wmv", ".3gp", ".rmvb", ".rm", ".vob", ".iso",
    ".txt", ".pdf", ".md", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".html", ".htm", ".url", ".chm", ".epub", ".mobi",
    ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".001", ".002", ".part",
    ".exe", ".dll", ".apk", ".ini", ".db", ".json", ".xml", ".yaml", ".yml", ".log", ".torrent", ".ug-tmp", ".tmp", ".bak",
}

_DEFAULT_IGNORED_DIRS = {
    ".git", "@eaDir", "$RECYCLE.BIN", "System Volume Information",
    "__MACOSX", ".Spotlight-V100", ".Trashes", "iPod Photo Cache",
    "TORRENT", "Torrent", "torrent",
}


def _fast_walk(root_path: Path, ignored_dirs: Optional[set[str]] = None):
    """
    针对 SMB / 9p / DrvFs 网络挂载优化的零冗余 stat 目录遍历器：
    - 标准 os.walk 在 d_type=DT_UNKNOWN 的 9p 文件系统上会对每个媒体文件发起 lstat RPC。
    - 本遍历器对已知文件扩展名直接短路归入 filenames，省去 99% 的网络 stat RPC，提速 10x~20x。
    """
    skip_dirs = _DEFAULT_IGNORED_DIRS if ignored_dirs is None else (_DEFAULT_IGNORED_DIRS | ignored_dirs)
    stack = [str(root_path)]
    while stack:
        current = stack.pop()
        dirnames: list[str] = []
        filenames: list[str] = []
        try:
            with os.scandir(current) as it:
                for entry in it:
                    name = entry.name
                    if name.startswith(".") or name in skip_dirs:
                        continue
                    dot = name.rfind(".")
                    ext = name[dot:].lower() if dot > 0 else ""
                    is_numbered_format_dir = dot > 0 and name[:dot].strip().isdigit() and name[dot + 1 :].isupper()
                    if ext in _NON_DIR_EXTS and not is_numbered_format_dir:
                        filenames.append(name)
                    else:
                        try:
                            if entry.is_dir(follow_symlinks=False):
                                dirnames.append(name)
                            else:
                                filenames.append(name)
                        except OSError:
                            pass
        except OSError:
            continue

        dirnames.sort()
        filenames.sort()
        yield current, dirnames, filenames

        # 支持调用方通过修改 dirnames[:] 原地剪枝子目录遍历
        for d in reversed(dirnames):
            stack.append(os.path.join(current, d))


def _scan_atomic_work_directory(
    session: Session,
    work_dir: Path,
    root_path: Path,
    existing_files_by_path: dict,
    recursive: bool = True,
    ignored_dirs: Optional[set[str]] = None,
) -> tuple[int, int]:
    """将带标准编号的独立作品/专辑目录或画册图包目录整体作为唯一的最小原子单元 (AssetUnit) 纳管"""
    from app.core.path_resolver import is_network_or_nas_path
    from app.core.config import SUPPORTED_AUDIO_EXTS

    all_detected = []
    if recursive:
        walker = _fast_walk(work_dir, ignored_dirs)
    else:
        try:
            _, _, f_list = next(_fast_walk(work_dir, ignored_dirs))
            walker = [(str(work_dir), [], f_list)]
        except StopIteration:
            walker = []

    for sub_dirpath, _, sub_filenames in walker:
        sub_dir = Path(sub_dirpath)
        sub_media = [
            sub_dir / fn for fn in sub_filenames
            if (sub_dir / fn).suffix.lower() in ALL_MEDIA_EXTS
        ]
        if not sub_media:
            continue
        rel_sub = ""
        if sub_dir != work_dir:
            try:
                rel_sub = str(sub_dir.relative_to(work_dir))
            except ValueError:
                rel_sub = sub_dir.name
        for du in analyze_folder_for_bundles(sub_dir, sub_media):
            all_detected.append((du, rel_sub))

    if not all_detected:
        return 0, 0

    # 检查是否已有主文件被纳管
    for du, _ in all_detected:
        p_str = os.path.abspath(str(du.primary_file))
        existing_f = existing_files_by_path.get(p_str)
        if existing_f and existing_f.asset_unit_id:
            return 0, 0

    col_folder = work_dir.parent if recursive else work_dir
    collection = get_or_create_collection_hierarchy(session, col_folder, root_path)
    work_abs = os.path.abspath(str(work_dir))
    is_nas = is_network_or_nas_path(work_abs)
    now_utc = datetime.now(timezone.utc)

    track_dus = [(du, rel_sub) for du, rel_sub in all_detected if du.unit_type in ("audio", "video", "bundle")]
    image_dus = [(du, rel_sub) for du, rel_sub in all_detected if du.unit_type == "image"]

    audio_cnt = sum(
        1 for du, _ in track_dus
        if du.unit_type == "audio" or (du.unit_type == "bundle" and du.primary_file.suffix.lower() in SUPPORTED_AUDIO_EXTS)
    )
    video_cnt = len(track_dus) - audio_cnt
    has_audio = audio_cnt > 0
    has_video = video_cnt > 0

    # 主媒体类型判定：含音轨则为 audio；若无音轨且图片数量显著多于附带短视频（如 90P-1V 复合画册），则归为 image 画册；否则归为 video
    if has_audio:
        unit_type = "audio"
    elif len(image_dus) > len(track_dus):
        unit_type = "image"
    elif has_video:
        unit_type = "video"
    else:
        unit_type = "image"

    unit = AssetUnit(
        title=work_dir.name,
        unit_type=unit_type,
        collection_id=collection.id if collection else None,
        dynamic_attributes={"is_atomic_work": True, "folder_path": work_abs},
    )
    session.add(unit)
    session.flush()

    files_scanned = 0
    total_duration = 0.0

    def _prepare_file(p_file: Path, role: str) -> AssetFile:
        nonlocal files_scanned
        resolved = os.path.abspath(str(p_file))
        if resolved in existing_files_by_path:
            return existing_files_by_path[resolved]
        if is_nas:
            f_size = 0
            f_mtime = now_utc
        else:
            stat = p_file.stat()
            f_size = stat.st_size
            f_mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        mime, _ = mimetypes.guess_type(str(p_file))
        f_rec = AssetFile(
            file_path=resolved,
            file_name=p_file.name,
            extension=p_file.suffix.lower(),
            mime_type=mime or "application/octet-stream",
            file_size=f_size,
            modified_at=f_mtime,
            asset_unit_id=unit.id,
            role=role,
        )
        session.add(f_rec)
        existing_files_by_path[resolved] = f_rec
        files_scanned += 1
        return f_rec

    prepared_tracks = []
    prepared_gallery = []
    seen_gallery_paths = set()
    has_primary_assigned = False
    has_cover_assigned = False
    first_cover_rec: Optional[AssetFile] = None
    first_primary_rec: Optional[AssetFile] = None

    # 若是图片主导的图包且含有图片，将首张图片设为 primary 兼 cover；否则将首个音视频轨设为 primary
    primary_from_image = (unit_type == "image" and len(image_dus) > 0)

    for du, rel_sub in track_dus:
        dur = None
        if not is_nas:
            _, _, dur = get_media_dimensions_and_duration(du.primary_file)
        if dur:
            total_duration += dur
        if not primary_from_image and not has_primary_assigned:
            p_role = "primary"
            has_primary_assigned = True
        else:
            p_role = "video" if du.unit_type in ("video", "bundle") and du.primary_file.suffix.lower() not in SUPPORTED_AUDIO_EXTS else "audio"
        p_rec = _prepare_file(du.primary_file, p_role)
        if first_primary_rec is None:
            first_primary_rec = p_rec

        sub_rec = None
        lyr_rec = None
        for comp_path, comp_role in du.files:
            if comp_role == "primary":
                continue
            if comp_role == "cover":
                c_role = "cover" if not has_cover_assigned else "image"
                has_cover_assigned = True
                c_rec = _prepare_file(comp_path, c_role)
                if first_cover_rec is None:
                    first_cover_rec = c_rec
                if c_rec.file_path not in seen_gallery_paths:
                    seen_gallery_paths.add(c_rec.file_path)
                    prepared_gallery.append((comp_path.stem, c_rec, comp_path.name, rel_sub))
            else:
                comp_rec = _prepare_file(comp_path, comp_role)
                if comp_role == "subtitle" and sub_rec is None:
                    sub_rec = comp_rec
                elif comp_role == "lyrics" and lyr_rec is None:
                    lyr_rec = comp_rec

        prepared_tracks.append((du.title, du.unit_type, p_rec, sub_rec, lyr_rec, dur, rel_sub))

    for du, rel_sub in image_dus:
        if not has_primary_assigned:
            img_role = "primary"
            has_primary_assigned = True
            has_cover_assigned = True
        elif not has_cover_assigned:
            img_role = "cover"
            has_cover_assigned = True
        else:
            img_role = "image"
        img_rec = _prepare_file(du.primary_file, img_role)
        if first_cover_rec is None:
            first_cover_rec = img_rec
        if first_primary_rec is None:
            first_primary_rec = img_rec
        if img_rec.file_path not in seen_gallery_paths:
            seen_gallery_paths.add(img_rec.file_path)
            prepared_gallery.append((du.title, img_rec, du.primary_file.name, rel_sub))

    # 单次批量 flush 生成所有 AssetFile 主键 ID，比逐文件 flush 提速 50 倍
    session.flush()

    tracks_manifest = [
        {
            "title": title,
            "unit_type": utype,
            "audio_file_id": p_rec.id,
            "subtitle_file_id": sub_rec.id if sub_rec else None,
            "lyrics_file_id": lyr_rec.id if lyr_rec else None,
            "duration_seconds": dur,
            "sub_folder": rel_sub,
        }
        for title, utype, p_rec, sub_rec, lyr_rec, dur, rel_sub in prepared_tracks
    ]

    gallery_manifest = [
        {
            "title": g_title,
            "file_id": g_rec.id,
            "file_name": g_fname,
            "sub_folder": g_sub,
        }
        for g_title, g_rec, g_fname, g_sub in prepared_gallery
    ]

    cover_file_id = first_cover_rec.id if first_cover_rec else (first_primary_rec.id if first_primary_rec else None)
    unit.cover_file_id = cover_file_id
    unit.duration_seconds = total_duration if total_duration > 0 else None
    unit.dynamic_attributes = {
        "is_atomic_work": True,
        "folder_path": work_abs,
        "audio_count": audio_cnt,
        "video_count": video_cnt,
        "track_count": len(tracks_manifest),
        "image_count": len(gallery_manifest),
        "tracks": tracks_manifest,
        "gallery": gallery_manifest,
    }
    session.add(unit)
    if collection and not collection.cover_asset_id:
        collection.cover_asset_id = unit.id
        session.add(collection)
    session.commit()
    return files_scanned, 1


def scan_directory(session: Session, root_path_str: str) -> dict:
    """非破坏性扫描指定物理目录并完成单元建模与系列归纳"""
    from app.core.user_rules import load_user_rules

    root_path = Path(root_path_str).resolve()
    if not root_path.exists() or not root_path.is_dir():
        return {"error": f"Path {root_path_str} does not exist or is not a directory"}

    # Register LibraryRoot
    lib = session.exec(select(LibraryRoot).where(LibraryRoot.path == str(root_path))).first()
    if not lib:
        lib = LibraryRoot(path=str(root_path), name=root_path.name or "本地目录")
        session.add(lib)
    lib.last_scanned_at = datetime.now(timezone.utc)
    session.commit()

    user_rules = load_user_rules()
    ignored_dirs = set(user_rules.ignored_dir_names)
    atomic_album_set = set(user_rules.atomic_album_containers)
    bucket_set = set(user_rules.container_bucket_dirs)

    total_files_scanned = 0
    total_units_created = 0

    # 预加载已纳管文件字典与原子作品目录集合，消除循环内的 N+1 SQL 查询与重复子目录遍历
    existing_files_by_path = {
        f.file_path: f for f in session.exec(select(AssetFile)).all()
    }
    existing_atomic_folders = {
        (u.dynamic_attributes or {}).get("folder_path")
        for u in session.exec(select(AssetUnit)).all()
        if (u.dynamic_attributes or {}).get("is_atomic_work") and (u.dynamic_attributes or {}).get("folder_path")
    }

    # 递归遍历所有文件夹 (使用零冗余 stat 的 _fast_walk)
    for dirpath, dirnames, filenames in _fast_walk(root_path, ignored_dirs):
        current_dir = Path(dirpath)
        cur_abs_path = os.path.abspath(str(current_dir))

        # 0. 若当前目录已是数据库纳管的完整原子作品目录，直接 O(1) 剪枝跳过内部遍历
        if cur_abs_path in existing_atomic_folders:
            dirnames[:] = []
            continue

        # 1. 若当前文件夹是带标准目录编号的作品/专辑目录，将其整体作为唯一的最小原子单元 (AssetUnit)，不再拆分内部子文件夹
        if WORK_CODE_REGEX.search(current_dir.name):
            dirnames[:] = []
            f_cnt, u_cnt = _scan_atomic_work_directory(
                session, current_dir, root_path, existing_files_by_path, recursive=True, ignored_dirs=ignored_dirs
            )
            total_files_scanned += f_cnt
            total_units_created += u_cnt
            continue

        # 2. 若当前目录位于 atomic_album_containers (如多页画册、漫画合集、摄影图集) 分类树下且自身不是分类容器桶：
        try:
            rel_parts = current_dir.relative_to(root_path).parts
        except ValueError:
            rel_parts = ()

        if (
            rel_parts
            and any(p in atomic_album_set for p in current_dir.parts)
            and current_dir.name not in bucket_set
            and (current_dir.name not in atomic_album_set or not dirnames)
        ):
            non_acc_dirs = [d for d in dirnames if not (is_accessory_collection_name(d) or DISC_REGEX.search(d))]
            direct_media_cnt = sum(1 for fn in filenames if (current_dir / fn).suffix.lower() in ALL_MEDIA_EXTS)
            # 若没有非附属子目录 (即叶级图包，或仅含 JPG/PNG/MP4/GIF/特典 等格式附属子目录，或单子夹嵌套包)，整包合并为 1 个原子 AssetUnit
            if not non_acc_dirs or (len(non_acc_dirs) == 1 and direct_media_cnt <= 2):
                dirnames[:] = []
                f_cnt, u_cnt = _scan_atomic_work_directory(
                    session, current_dir, root_path, existing_files_by_path, recursive=True, ignored_dirs=ignored_dirs
                )
                total_files_scanned += f_cnt
                total_units_created += u_cnt
                continue
            elif direct_media_cnt >= 4:
                # 既有下级独立子图包，自身又直接包含多张图片 (如合集第一辑直接放图，第二辑在子文件夹)，将本层直属文件合并为 1 个原子单元并继续遍历子目录
                f_cnt, u_cnt = _scan_atomic_work_directory(
                    session, current_dir, root_path, existing_files_by_path, recursive=False, ignored_dirs=ignored_dirs
                )
                total_files_scanned += f_cnt
                total_units_created += u_cnt
                continue

        # 收集该文件夹下受支持的媒体文件
        media_files = []
        for fn in filenames:
            p = current_dir / fn
            if p.suffix.lower() in ALL_MEDIA_EXTS:
                media_files.append(p)

        if not media_files:
            continue

        # 运行聚类与复合包检测
        detected_units = analyze_folder_for_bundles(current_dir, media_files)

        # 如果同目录存在音频/视频单元且当前目录不是散装分类桶，则同目录内剩余的图片不作为孤立图片单元，而是挂载到首个音视频单元作为附属插画
        has_av_in_folder = any(u.unit_type in ("audio", "video", "bundle") for u in detected_units)
        if has_av_in_folder and current_dir.name not in bucket_set:
            av_units = [u for u in detected_units if u.unit_type in ("audio", "video", "bundle")]
            img_units = [u for u in detected_units if u.unit_type == "image"]
            if img_units and av_units:
                existing_comp_paths = {p for p, _ in av_units[0].files}
                for iu in img_units:
                    if iu.primary_file not in existing_comp_paths:
                        av_units[0].files.append((iu.primary_file, "image"))
                detected_units = av_units

        # 检查是否需要关联或生成该文件夹对应的系列 Collection
        collection = None

        for du in detected_units:
            # 检查主文件是否已登记 (纯内存 O(1) 查表，零网络/磁盘 I/O)
            primary_path_str = os.path.abspath(str(du.primary_file))
            existing_primary_file = existing_files_by_path.get(primary_path_str)

            if existing_primary_file and existing_primary_file.asset_unit_id:
                # 主文件已纳管：检查是否有新增的伴随文件 (subtitle / lyrics / cover / audio) 需要挂载
                existing_unit_id = existing_primary_file.asset_unit_id
                for p_file, role in du.files:
                    if role == "primary":
                        continue
                    resolved_comp = os.path.abspath(str(p_file))
                    existing_comp = existing_files_by_path.get(resolved_comp)
                    if not existing_comp:
                        from app.core.path_resolver import is_network_or_nas_path
                        if is_network_or_nas_path(resolved_comp):
                            f_size = 0
                            f_mtime = datetime.now(timezone.utc)
                        else:
                            stat = p_file.stat()
                            f_size = stat.st_size
                            f_mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
                        mime, _ = mimetypes.guess_type(str(p_file))
                        comp_record = AssetFile(
                            file_path=resolved_comp,
                            file_name=p_file.name,
                            extension=p_file.suffix.lower(),
                            mime_type=mime or "application/octet-stream",
                            file_size=f_size,
                            modified_at=f_mtime,
                            asset_unit_id=existing_unit_id,
                            role=role,
                        )
                        session.add(comp_record)
                        existing_files_by_path[resolved_comp] = comp_record
                        total_files_scanned += 1
                continue

            if collection is None:
                collection = get_or_create_collection_hierarchy(session, current_dir, root_path)

            # 标记附属子目录元数据 (插画/花絮/分流等)
            unit_attrs = {}
            cur_abs = os.path.abspath(str(current_dir))
            if collection and collection.folder_path and cur_abs.startswith(collection.folder_path):
                rel_sub = cur_abs[len(collection.folder_path):].lstrip('/\\')
                if rel_sub:
                    unit_attrs["sub_folder"] = rel_sub
                    unit_attrs["is_subfolder_item"] = True

            if is_accessory_collection_name(current_dir.name):
                unit_attrs["is_accessory"] = True
                unit_attrs["accessory_folder"] = current_dir.name
                if du.unit_type == "image":
                    unit_attrs["role"] = "illustration"
                else:
                    unit_attrs["role"] = "bonus"

            from app.core.path_resolver import is_network_or_nas_path
            is_nas_file = is_network_or_nas_path(primary_path_str)

            # 提取音画尺寸与播放时长 (NAS/网络盘采用延迟按需加载，避免扫描时 thousands of SMB RPCs)
            if is_nas_file:
                w, h, dur = None, None, None
            else:
                w, h, dur = get_media_dimensions_and_duration(du.primary_file)
                if du.unit_type == "image":
                    dur = None
                elif du.unit_type == "audio":
                    w = None
                    h = None

            # 创建 AssetUnit
            unit = AssetUnit(
                title=du.title,
                unit_type=du.unit_type,
                collection_id=collection.id if collection else None,
                duration_seconds=dur,
                width=w,
                height=h,
                dynamic_attributes=unit_attrs,
            )
            session.add(unit)
            session.flush()
            total_units_created += 1

            # 登记附属物理文件（若共享文件夹封面已登记则直接复用其 AssetFile 记录）
            primary_file_record = None
            cover_file_record = None
            now_utc = datetime.now(timezone.utc)
            for p_file, role in du.files:
                resolved_path = os.path.abspath(str(p_file))
                existing_f = existing_files_by_path.get(resolved_path)
                if existing_f:
                    if role == "cover":
                        cover_file_record = existing_f
                    elif role == "primary":
                        primary_file_record = existing_f
                    continue
                if is_nas_file:
                    f_size = 0
                    f_mtime = now_utc
                else:
                    stat = p_file.stat()
                    f_size = stat.st_size
                    f_mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
                mime, _ = mimetypes.guess_type(str(p_file))
                f_record = AssetFile(
                    file_path=resolved_path,
                    file_name=p_file.name,
                    extension=p_file.suffix.lower(),
                    mime_type=mime or "application/octet-stream",
                    file_size=f_size,
                    modified_at=f_mtime,
                    asset_unit_id=unit.id,
                    role=role,
                )
                session.add(f_record)
                existing_files_by_path[resolved_path] = f_record
                total_files_scanned += 1
                if role == "primary":
                    primary_file_record = f_record
                elif role == "cover":
                    cover_file_record = f_record

            session.flush()

            if cover_file_record:
                unit.cover_file_id = cover_file_record.id
                session.add(unit)
            elif primary_file_record:
                unit.cover_file_id = primary_file_record.id
                session.add(unit)

            # 如果系列没有封面，顺手用第一个单元作为系列封面
            if collection and not collection.cover_asset_id:
                collection.cover_asset_id = unit.id
                session.add(collection)

        session.commit()

            # 缩略图采用延迟按需生成 (Lazy On-Demand by /api/stream/thumbnail)，避免阻塞扫描大库

    session.commit()
    return {
        "status": "success",
        "root": str(root_path),
        "total_files": total_files_scanned,
        "total_units": total_units_created
    }
