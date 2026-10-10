import os
import mimetypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from sqlmodel import Session, select
from app.core.config import ALL_MEDIA_EXTS
from app.models.entities import Collection, AssetUnit, AssetFile, LibraryRoot
from app.services.bundle_detector import analyze_folder_for_bundles
from app.services.media_processor import get_media_dimensions_and_duration, get_or_create_unit_thumbnail

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

def scan_directory(session: Session, root_path_str: str) -> dict:
    """非破坏性扫描指定物理目录并完成单元建模与系列归纳"""
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

    total_files_scanned = 0
    total_units_created = 0

    # 递归遍历所有文件夹
    for dirpath, dirnames, filenames in os.walk(root_path):
        current_dir = Path(dirpath)
        
        # 收集该文件夹下受支持的媒体文件
        media_files = []
        for fn in filenames:
            p = current_dir / fn
            if p.suffix.lower() in ALL_MEDIA_EXTS:
                media_files.append(p)

        if not media_files:
            continue

        # 关联或生成该文件夹对应的系列 Collection
        collection = get_or_create_collection_hierarchy(session, current_dir, root_path)

        # 运行聚类与复合包检测
        detected_units = analyze_folder_for_bundles(current_dir, media_files)

        for du in detected_units:
            # 检查主文件是否已登记
            primary_path_str = str(du.primary_file.resolve())
            existing_primary_file = session.exec(
                select(AssetFile).where(AssetFile.file_path == primary_path_str)
            ).first()

            if existing_primary_file and existing_primary_file.asset_unit_id:
                # 已经纳管，跳过或更新
                continue

            # 探测音视频宽高和时长
            w, h, dur = get_media_dimensions_and_duration(du.primary_file)

            # 创建 AssetUnit
            unit = AssetUnit(
                title=du.title,
                unit_type=du.unit_type,
                collection_id=collection.id if collection else None,
                duration_seconds=dur,
                width=w,
                height=h,
            )
            session.add(unit)
            session.commit()
            session.refresh(unit)
            total_units_created += 1

            # 登记附属物理文件
            primary_file_record = None
            cover_file_record = None
            for p_file, role in du.files:
                stat = p_file.stat()
                mime, _ = mimetypes.guess_type(str(p_file))
                f_record = AssetFile(
                    file_path=str(p_file.resolve()),
                    file_name=p_file.name,
                    extension=p_file.suffix.lower(),
                    mime_type=mime or "application/octet-stream",
                    file_size=stat.st_size,
                    modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                    asset_unit_id=unit.id,
                    role=role,
                )
                session.add(f_record)
                session.commit()
                session.refresh(f_record)
                total_files_scanned += 1
                if role == "primary":
                    primary_file_record = f_record
                elif role == "cover":
                    cover_file_record = f_record

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

            # 触发缩略图预生成
            try:
                get_or_create_unit_thumbnail(unit.id, str(du.primary_file), unit.unit_type)
            except Exception as e:
                print(f"Thumbnail generation error for unit {unit.id}: {e}")

    return {
        "status": "success",
        "root": str(root_path),
        "total_files": total_files_scanned,
        "total_units": total_units_created
    }
