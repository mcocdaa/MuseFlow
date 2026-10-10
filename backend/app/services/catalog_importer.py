import importlib.util
import json
import logging
import mimetypes
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import httpx
from mutagen import File as MutagenFile
from mutagen.flac import FLAC
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4
from sqlmodel import Session, select

from app.core.config import (
    DATA_DIR,
    THUMBNAILS_DIR,
    ALL_MEDIA_EXTS,
    SUPPORTED_AUDIO_EXTS,
    SUPPORTED_VIDEO_EXTS,
    SUPPORTED_IMAGE_EXTS,
    SUPPORTED_SUBTITLE_EXTS,
)
from app.core.path_resolver import resolve_physical_path
from app.models.entities import AssetFile, AssetUnit, Collection, Superset, SupersetUnitLink, LibraryRoot

logger = logging.getLogger("museflow.catalog_importer")

COVER_CACHE_DIR = DATA_DIR / "cache" / "covers"
COVER_CACHE_DIR.mkdir(parents=True, exist_ok=True)
PLUGINS_DIR = DATA_DIR / "plugins"

# Generic catalog work identifier pattern (e.g. AB123456, ISBN/ISRC/Catalog prefix + digits)
WORK_CODE_PATTERN = re.compile(r"([A-Z]{2,4}\d{5,8})", re.IGNORECASE)


def extract_work_code(text: str) -> Optional[str]:
    """Extracts generic catalog work code from directory or file name."""
    if not text:
        return None
    m = WORK_CODE_PATTERN.search(text)
    if m:
        return m.group(1).upper()
    return None


def _load_external_catalog_plugin():
    """Dynamically loads an optional user-provided catalog metadata plugin from DATA_DIR/plugins."""
    if not PLUGINS_DIR.exists():
        return None
    for plugin_path in sorted(PLUGINS_DIR.glob("*_plugin.py")):
        try:
            spec = importlib.util.spec_from_file_location(plugin_path.stem, plugin_path)
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                if hasattr(mod, "fetch_remote_catalog_meta"):
                    return mod
        except Exception as e:
            logger.warning(f"Failed to load external catalog plugin {plugin_path}: {e}")
    return None


def fetch_and_cache_catalog_meta(
    work_code: str,
    client: Optional[httpx.Client] = None,
    download_cover: bool = True,
) -> Optional[dict]:
    """
    Loads work metadata from local cache or delegates to an optional external user plugin
    located in DATA_DIR/plugins/. Core repository contains zero domain-specific endpoints.
    """
    cache_meta_file = COVER_CACHE_DIR / f"{work_code}.json"

    if cache_meta_file.exists():
        try:
            with open(cache_meta_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data:
                    if "code" not in data:
                        data["code"] = work_code
                    return data
        except Exception:
            pass

    plugin = _load_external_catalog_plugin()
    if plugin and hasattr(plugin, "fetch_remote_catalog_meta"):
        try:
            return plugin.fetch_remote_catalog_meta(
                work_code=work_code,
                cache_dir=COVER_CACHE_DIR,
                client=client,
                download_cover=download_cover,
            )
        except Exception as e:
            logger.warning(f"External catalog plugin failed for {work_code}: {e}")

    return None


def get_audio_duration_fast(file_path: Path) -> Optional[float]:
    """Ultra-fast header-based audio duration extraction, reading only 44 bytes for WAV to prevent SMB network latency."""
    ext = file_path.suffix.lower()
    try:
        if ext == ".wav":
            try:
                with open(file_path, "rb") as f:
                    h = f.read(44)
                    if len(h) >= 32 and h[:4] == b"RIFF":
                        import struct
                        byterate = struct.unpack("<I", h[28:32])[0]
                        if byterate > 0:
                            sz = file_path.stat().st_size
                            return round((sz - 44) / byterate, 2)
            except Exception:
                pass
            return None
        elif ext == ".mp3":
            m = MP3(file_path)
            return round(float(m.info.length), 2)
        elif ext == ".flac":
            fl = FLAC(file_path)
            return round(float(fl.info.length), 2)
        elif ext in (".m4a", ".mp4"):
            mp = MP4(file_path)
            return round(float(mp.info.length), 2)
        else:
            audio = MutagenFile(file_path)
            if audio and hasattr(audio, "info") and hasattr(audio.info, "length"):
                return round(float(audio.info.length), 2)
    except Exception:
        pass
    return None


def fast_scan_folder_media(folder: Path, max_depth: int = 4) -> List[Path]:
    """Shallow recursive scan to avoid SMB latency bottlenecks, exploring up to depth 4."""
    results: List[Path] = []

    def _walk(curr: Path, depth: int):
        if depth > max_depth:
            return
        try:
            with os.scandir(curr) as it:
                for entry in it:
                    if entry.is_file(follow_symlinks=False):
                        ext = os.path.splitext(entry.name)[1].lower()
                        if ext in ALL_MEDIA_EXTS:
                            results.append(Path(entry.path))
                    elif entry.is_dir(follow_symlinks=False):
                        if depth > 1 and extract_work_code(entry.name):
                            continue
                        if depth + 1 <= max_depth:
                            _walk(Path(entry.path), depth + 1)
        except Exception:
            pass

    _walk(folder, 1)
    return results


def discover_audio_work_targets(base_path: Path, max_depth: int = 4) -> Tuple[List[Tuple[Path, Optional[str]]], List[Path]]:
    """
    通用递归探测多媒体与音频专辑工作单元（零硬编码，支持任意用户目录拓扑）：
    1. 顶层散落媒体直接归集为 loose_media_files；
    2. 递归遍历目录（深度<=max_depth）：
       - 若某子目录名命中标准作品编号正则，将其作为独立作品单元收录，不再向内部细分；
       - 若某子目录不含编号，检查其直接下属文件：若包含媒体文件，则作为一个独立作品系列收录；
       - 若其包含命中了编号的子文件夹，则继续递归挖掘。
    """
    work_targets: List[Tuple[Path, Optional[str]]] = []
    loose_media_files: List[Path] = []

    def _walk_dir(curr_path: Path, depth: int):
        if depth > max_depth:
            return

        wcode = extract_work_code(curr_path.name)
        if wcode and depth > 0:
            work_targets.append((curr_path, wcode))
            return

        has_direct_media = False
        sub_dirs: List[Path] = []

        try:
            with os.scandir(curr_path) as it:
                for entry in it:
                    if entry.is_file(follow_symlinks=False):
                        ext = os.path.splitext(entry.name)[1].lower()
                        if ext in ALL_MEDIA_EXTS:
                            if depth == 0:
                                loose_media_files.append(Path(entry.path))
                            else:
                                has_direct_media = True
                    elif entry.is_dir(follow_symlinks=False):
                        sub_dirs.append(Path(entry.path))
        except Exception:
            return

        has_nested_coded = any(extract_work_code(d.name) for d in sub_dirs)

        if depth > 0 and has_direct_media and not has_nested_coded:
            work_targets.append((curr_path, None))

        for d in sorted(sub_dirs):
            _walk_dir(d, depth + 1)

    _walk_dir(base_path, 0)
    return work_targets, loose_media_files


def import_catalog_library(
    session: Session,
    base_folder_str: str,
    extra_folders: Optional[List[str]] = None,
) -> dict:
    """
    通用多媒体与音频专辑库扫描服务：
    递归索引指定目录，智能提取元数据与封面，建立 Collection 和 AssetUnit 映射。
    """
    base_path = resolve_physical_path(base_folder_str)
    if not base_path.exists():
        return {"error": f"Base path does not exist: {base_path}"}

    lib = session.exec(select(LibraryRoot).where(LibraryRoot.path == str(base_path))).first()
    if not lib:
        lib = LibraryRoot(path=str(base_path), name=f"媒体库 ({base_path.name})")
        session.add(lib)
    lib.last_scanned_at = datetime.now(timezone.utc)
    session.commit()

    http_client = httpx.Client(timeout=12, headers={"User-Agent": "Mozilla/5.0"})

    created_collections = 0
    created_units = 0
    created_files = 0

    work_targets, loose_media_files = discover_audio_work_targets(base_path)

    if extra_folders:
        for ef in extra_folders:
            ep = resolve_physical_path(ef)
            if ep.exists() and ep.is_dir():
                sub_targets, sub_loose = discover_audio_work_targets(ep)
                work_targets.extend(sub_targets)
                loose_media_files.extend(sub_loose)

    logger.info(f"Identified {len(work_targets)} discrete works/series to ingest from {base_path}")

    all_imported_unit_ids: List[int] = []
    video_unit_ids: List[int] = []

    if loose_media_files:
        col = session.exec(select(Collection).where(Collection.folder_path == str(base_path))).first()
        if not col:
            col = Collection(name="其他散落媒体", folder_path=str(base_path), description="顶层散落音频与短片")
            session.add(col)
            session.commit()
            session.refresh(col)
            created_collections += 1

        for f in loose_media_files:
            existing = session.exec(select(AssetFile).where(AssetFile.file_path == str(f))).first()
            if existing and existing.asset_unit_id:
                all_imported_unit_ids.append(existing.asset_unit_id)
                continue

            u_type = "video" if f.suffix.lower() in SUPPORTED_VIDEO_EXTS else "audio"
            dur = get_audio_duration_fast(f) if u_type == "audio" else None
            unit = AssetUnit(
                title=f.stem,
                unit_type=u_type,
                collection_id=col.id,
                duration_seconds=dur,
                created_at=datetime.now(timezone.utc)
            )
            session.add(unit)
            session.commit()
            session.refresh(unit)
            created_units += 1
            all_imported_unit_ids.append(unit.id)
            if u_type == "video":
                video_unit_ids.append(unit.id)

            mime, _ = mimetypes.guess_type(f.name)
            p_file = AssetFile(
                file_path=str(f),
                file_name=f.name,
                extension=f.suffix.lower(),
                mime_type=mime or "application/octet-stream",
                file_size=f.stat().st_size if f.exists() else 0,
                modified_at=datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc),
                asset_unit_id=unit.id,
                role="primary"
            )
            session.add(p_file)
            created_files += 1
            session.commit()

    total_targets = len(work_targets)
    for idx, (folder, work_code) in enumerate(work_targets, 1):
        folder_name = folder.name
        logger.info(f"[{idx}/{total_targets}] Ingesting: {folder_name} (Code: {work_code})")

        meta = None
        if work_code:
            meta = fetch_and_cache_catalog_meta(work_code, http_client)

        col = session.exec(select(Collection).where(Collection.folder_path == str(folder))).first()
        if not col:
            if meta and meta.get("title"):
                col_name = f"[{work_code}] {meta['title']}"
                desc_parts = []
                if meta.get("circle"):
                    desc_parts.append(f"创作者: {meta['circle']}")
                if meta.get("vas"):
                    desc_parts.append(f"演职员: {', '.join(meta['vas'])}")
                if meta.get("tags"):
                    desc_parts.append(f"标签: {', '.join(meta['tags'])}")
                col_desc = " | ".join(desc_parts)
            else:
                col_name = folder_name
                col_desc = f"媒体系列: {folder_name}"

            col = Collection(
                name=col_name,
                folder_path=str(folder),
                description=col_desc
            )
            session.add(col)
            session.commit()
            session.refresh(col)
            created_collections += 1
        elif meta and (not col.description or "创作者:" not in col.description):
            if meta.get("title") and work_code and not col.name.startswith(f"[{work_code}"):
                col.name = f"[{work_code}] {meta['title']}"
            desc_parts = []
            if meta.get("circle"):
                desc_parts.append(f"创作者: {meta['circle']}")
            if meta.get("vas"):
                desc_parts.append(f"演职员: {', '.join(meta['vas'])}")
            if meta.get("tags"):
                desc_parts.append(f"标签: {', '.join(meta['tags'])}")
            col.description = " | ".join(desc_parts)
            session.add(col)
            session.commit()

        media_files = fast_scan_folder_media(folder, max_depth=4)
        if not media_files:
            continue

        audio_files = [f for f in media_files if f.suffix.lower() in SUPPORTED_AUDIO_EXTS]
        video_files = [f for f in media_files if f.suffix.lower() in SUPPORTED_VIDEO_EXTS]
        subtitle_files = [f for f in media_files if f.suffix.lower() in SUPPORTED_SUBTITLE_EXTS]
        image_files = [f for f in media_files if f.suffix.lower() in SUPPORTED_IMAGE_EXTS]

        cached_cover_path = COVER_CACHE_DIR / f"{work_code}.jpg" if work_code else None

        cand_cover = None
        for img in image_files:
            f_l = img.name.lower()
            if any(k in f_l for k in ["cover", "封面", "jacket", "ジャケット", "main", "folder", "thumb", "poster"]):
                cand_cover = img
                break
        if not cand_cover and image_files:
            cand_cover = image_files[0]

        claimed_subtitles = set()
        col_first_unit_id = None

        track_groups: Dict[str, List[Path]] = {}
        for a_file in sorted(audio_files):
            key = a_file.stem.strip()
            if key not in track_groups:
                track_groups[key] = []
            track_groups[key].append(a_file)

        for track_title, files_in_track in track_groups.items():
            primary_file = next((f for f in files_in_track if f.suffix.lower() in ('.mp3', '.m4a')), files_in_track[0])
            alternate_files = [f for f in files_in_track if f != primary_file]

            unit = None
            for f in files_in_track:
                existing_file = session.exec(select(AssetFile).where(AssetFile.file_path == str(f))).first()
                if existing_file and existing_file.asset_unit_id:
                    unit = session.get(AssetUnit, existing_file.asset_unit_id)
                    if unit:
                        break

            companion_subs = []
            for s in subtitle_files:
                if str(s) in claimed_subtitles:
                    continue
                if s.stem == track_title or s.stem.startswith(track_title + ".") or s.name in (f"{primary_file.name}.vtt", f"{primary_file.name}.lrc"):
                    companion_subs.append(s)
                    claimed_subtitles.add(str(s))

            unit_type = "bundle" if (companion_subs or alternate_files) else "audio"
            duration = get_audio_duration_fast(primary_file)
            f_size = primary_file.stat().st_size if primary_file.exists() else 0

            if not unit:
                unit = AssetUnit(
                    title=track_title,
                    unit_type=unit_type,
                    collection_id=col.id,
                    duration_seconds=duration,
                    created_at=datetime.now(timezone.utc)
                )
                session.add(unit)
                session.commit()
                session.refresh(unit)
                created_units += 1
            else:
                unit.title = track_title
                unit.unit_type = unit_type
                if duration:
                    unit.duration_seconds = duration
                session.add(unit)
                session.commit()

            all_imported_unit_ids.append(unit.id)
            if not col_first_unit_id:
                col_first_unit_id = unit.id

            primary_path_str = str(primary_file)
            p_file = session.exec(select(AssetFile).where(AssetFile.file_path == primary_path_str)).first()
            mime, _ = mimetypes.guess_type(primary_file.name)
            if not p_file:
                p_file = AssetFile(
                    file_path=primary_path_str,
                    file_name=primary_file.name,
                    extension=primary_file.suffix.lower(),
                    mime_type=mime or "audio/mpeg",
                    file_size=f_size,
                    modified_at=datetime.fromtimestamp(primary_file.stat().st_mtime, tz=timezone.utc),
                    asset_unit_id=unit.id,
                    role="primary"
                )
                session.add(p_file)
                created_files += 1
            else:
                p_file.asset_unit_id = unit.id
                p_file.role = "primary"
                session.add(p_file)

            for alt_file in alternate_files:
                alt_path_str = str(alt_file)
                alt_f = session.exec(select(AssetFile).where(AssetFile.file_path == alt_path_str)).first()
                alt_mime, _ = mimetypes.guess_type(alt_file.name)
                alt_size = alt_file.stat().st_size if alt_file.exists() else 0
                if not alt_f:
                    alt_f = AssetFile(
                        file_path=alt_path_str,
                        file_name=alt_file.name,
                        extension=alt_file.suffix.lower(),
                        mime_type=alt_mime or "audio/x-wav",
                        file_size=alt_size,
                        modified_at=datetime.fromtimestamp(alt_file.stat().st_mtime, tz=timezone.utc),
                        asset_unit_id=unit.id,
                        role="lossless"
                    )
                    session.add(alt_f)
                    created_files += 1
                else:
                    alt_f.asset_unit_id = unit.id
                    alt_f.role = "lossless"
                    session.add(alt_f)

            for sub in companion_subs:
                sub_str = str(sub)
                existing_sub = session.exec(select(AssetFile).where(AssetFile.file_path == sub_str)).first()
                if existing_sub:
                    existing_sub.asset_unit_id = unit.id
                    existing_sub.role = "subtitle"
                    session.add(existing_sub)
                    continue
                sub_mime, _ = mimetypes.guess_type(sub.name)
                s_file = AssetFile(
                    file_path=sub_str,
                    file_name=sub.name,
                    extension=sub.suffix.lower(),
                    mime_type=sub_mime or "text/vtt",
                    file_size=sub.stat().st_size if sub.exists() else 0,
                    modified_at=datetime.fromtimestamp(sub.stat().st_mtime, tz=timezone.utc),
                    asset_unit_id=unit.id,
                    role="subtitle"
                )
                session.add(s_file)
                created_files += 1

            unit_thumb = THUMBNAILS_DIR / f"thumb_{unit.id}.jpg"
            if not unit_thumb.exists():
                if cached_cover_path and cached_cover_path.exists():
                    try:
                        shutil.copyfile(cached_cover_path, unit_thumb)
                    except Exception:
                        pass
                elif cand_cover and cand_cover.exists():
                    try:
                        shutil.copyfile(cand_cover, unit_thumb)
                    except Exception:
                        pass

            session.commit()

        if col_first_unit_id and not col.cover_asset_id:
            col.cover_asset_id = col_first_unit_id
            session.add(col)
            session.commit()

        for v_file in video_files:
            v_path_str = str(v_file)
            existing_file = session.exec(select(AssetFile).where(AssetFile.file_path == v_path_str)).first()
            if existing_file and existing_file.asset_unit_id:
                video_unit_ids.append(existing_file.asset_unit_id)
                continue

            v_size = v_file.stat().st_size if v_file.exists() else 0
            v_unit = AssetUnit(
                title=v_file.stem,
                unit_type="video",
                collection_id=col.id,
                created_at=datetime.now(timezone.utc)
            )
            session.add(v_unit)
            session.commit()
            session.refresh(v_unit)
            created_units += 1
            video_unit_ids.append(v_unit.id)

            mime, _ = mimetypes.guess_type(v_file.name)
            v_asset_file = AssetFile(
                file_path=v_path_str,
                file_name=v_file.name,
                extension=v_file.suffix.lower(),
                mime_type=mime or "video/mp4",
                file_size=v_size,
                modified_at=datetime.fromtimestamp(v_file.stat().st_mtime, tz=timezone.utc),
                asset_unit_id=v_unit.id,
                role="primary"
            )
            session.add(v_asset_file)
            created_files += 1
            session.commit()

    def ensure_superset(name: str, desc: str, icon: str, unit_ids: List[int]):
        if not unit_ids:
            return
        s = session.exec(select(Superset).where(Superset.name == name)).first()
        if not s:
            s = Superset(name=name, description=desc, icon=icon)
            session.add(s)
            session.commit()
            session.refresh(s)

        existing_links = session.exec(select(SupersetUnitLink.unit_id).where(SupersetUnitLink.superset_id == s.id)).all()
        existing_set = set(existing_links)
        for uid in set(unit_ids):
            if uid not in existing_set:
                session.add(SupersetUnitLink(superset_id=s.id, unit_id=uid))
                existing_set.add(uid)
        session.commit()

    ensure_superset(
        name="🎧 音频精选集 (Audio Hub)",
        desc="全部导入的专辑与音频系列合集",
        icon="sparkles",
        unit_ids=all_imported_unit_ids
    )

    if video_unit_ids:
        ensure_superset(
            name="🎬 专辑伴生视频/短片",
            desc="专辑目录附带的演示视频、PV 与短片集合",
            icon="film",
            unit_ids=video_unit_ids
        )

    http_client.close()

    return {
        "status": "success",
        "created_collections": created_collections,
        "created_units": created_units,
        "created_files": created_files,
        "total_units_imported": len(all_imported_unit_ids)
    }
