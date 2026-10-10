from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse, FileResponse
from sqlmodel import Session, select
from app.core.config import THUMBNAILS_DIR, DATA_DIR
from app.core.db import get_session
from app.core.path_resolver import resolve_physical_path, is_network_or_nas_path, is_nas_online, safe_path_exists, safe_is_dir
from app.models.entities import AssetFile, AssetUnit, Collection
from app.services.media_processor import get_or_create_unit_thumbnail, srt_to_vtt, lrc_to_vtt
import shutil
import re

COVER_CACHE_DIR = DATA_DIR / "cache" / "covers"
RJ_PATTERN = re.compile(r"(RJ\d{6,8}|VJ\d{6,8}|BJ\d{6,8})", re.IGNORECASE)

router = APIRouter(prefix="/api/stream", tags=["stream"])

def range_streamer(file_path: Path, start: int, end: int, chunk_size: int = 1024 * 1024):
    try:
        with open(file_path, "rb") as f:
            f.seek(start)
            bytes_to_read = end - start + 1
            while bytes_to_read > 0:
                current_chunk = min(bytes_to_read, chunk_size)
                data = f.read(current_chunk)
                if not data:
                    break
                bytes_to_read -= len(data)
                yield data
    except (OSError, IOError, TimeoutError):
        # Gracefully terminate generator on network/SMB dropouts without crashing
        return

@router.get("/file/{file_id}")
def stream_file(file_id: int, request: Request, session: Session = Depends(get_session)):
    """支持 HTTP 206 Range 范围请求的音视频流媒体传输，具备 SMB 网络容灾与透明路径映射"""
    asset_file = session.get(AssetFile, file_id)
    if not asset_file:
        raise HTTPException(status_code=404, detail="File record not found")

    is_nas = is_network_or_nas_path(asset_file.file_path)
    if is_nas and not is_nas_online():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="NAS 存储设备暂时离线或休眠中，请检查局域网连接或唤醒设备"
        )

    path = resolve_physical_path(asset_file.file_path)
    try:
        if not path.exists():
            if is_nas:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="NAS 存储设备暂时离线或休眠中，请检查局域网连接或唤醒设备"
                )
            raise HTTPException(status_code=404, detail="Physical file not found on disk")
        file_size = path.stat().st_size
    except HTTPException:
        raise
    except (OSError, IOError, TimeoutError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="NAS 存储设备网络响应超时或连接中断，请检查网络"
        )

    range_header = request.headers.get("Range")

    if range_header:
        # e.g., "bytes=0-1000" or "bytes=500-"
        try:
            byte_range = range_header.replace("bytes=", "").split("-")
            start = int(byte_range[0])
            end = int(byte_range[1]) if byte_range[1] else file_size - 1
            if start >= file_size:
                raise HTTPException(status_code=416, detail="Requested Range Not Satisfiable")
            end = min(end, file_size - 1)
            content_length = end - start + 1

            headers = {
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(content_length),
                "Content-Type": asset_file.mime_type or "application/octet-stream",
            }

            return StreamingResponse(
                range_streamer(path, start, end),
                status_code=status.HTTP_206_PARTIAL_CONTENT,
                headers=headers
            )
        except (ValueError, IndexError):
            pass

    # No range or invalid range
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(file_size),
        "Content-Type": asset_file.mime_type or "application/octet-stream",
    }
    return FileResponse(path, headers=headers, media_type=asset_file.mime_type)

@router.get("/thumbnail/{unit_id}")
def get_thumbnail(unit_id: int, session: Session = Depends(get_session)):
    """获取该原子单元的最佳预览缩略图（优先从本地 SSD 缓存服务，免疫 NAS 离线）"""
    # 极速路径：本地缩略图缓存命中则直接返回，完全不碰网络磁盘
    local_thumb = THUMBNAILS_DIR / f"thumb_{unit_id}.jpg"
    if local_thumb.exists():
        return FileResponse(local_thumb, media_type="image/jpeg")

    unit = session.get(AssetUnit, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="AssetUnit not found")

    # 优先检查系列封面本地缓存
    if unit.collection_id:
        local_col_thumb = THUMBNAILS_DIR / f"thumb_col_{unit.collection_id}.jpg"
        if local_col_thumb.exists():
            try:
                shutil.copyfile(local_col_thumb, local_thumb)
            except Exception:
                pass
            return FileResponse(local_col_thumb, media_type="image/jpeg")

        col = session.get(Collection, unit.collection_id)
        if col:
            m = RJ_PATTERN.search(col.name or "") or (RJ_PATTERN.search(col.folder_path or "") if col.folder_path else None)
            if m:
                rj_code = m.group(1).upper()
                cached_cover = COVER_CACHE_DIR / f"{rj_code}.jpg"
                if cached_cover.exists():
                    try:
                        shutil.copyfile(cached_cover, local_thumb)
                    except Exception:
                        pass
                    return FileResponse(cached_cover, media_type="image/jpeg")

    # 优先从 primary 文件生成或读取缩略图 (仅在非 NAS 或 NAS 在线时)
    primary_file = None
    if unit.cover_file_id:
        primary_file = session.get(AssetFile, unit.cover_file_id)
    if not primary_file:
        primary_file = session.exec(
            select(AssetFile).where(AssetFile.asset_unit_id == unit.id, AssetFile.role == "primary")
        ).first()

    if primary_file:
        is_nas = is_network_or_nas_path(primary_file.file_path)
        if not is_nas or is_nas_online():
            resolved_path = resolve_physical_path(primary_file.file_path)
            target_type = "image" if primary_file.extension.lower() in (".jpg", ".jpeg", ".png", ".webp") else unit.unit_type
            
            try:
                thumb_path = get_or_create_unit_thumbnail(unit.id, str(resolved_path), target_type)
                if thumb_path and Path(thumb_path).exists():
                    return FileResponse(thumb_path, media_type="image/jpeg")
            except Exception:
                pass

            # Fallback to serving the original file if it exists and is an image
            try:
                if resolved_path.exists() and primary_file.extension.lower() in (".jpg", ".jpeg", ".png", ".webp"):
                    return FileResponse(resolved_path, media_type=primary_file.mime_type)
            except Exception:
                pass

    raise HTTPException(status_code=404, detail="Thumbnail could not be generated")

@router.get("/collection_thumbnail/{collection_id}")
def get_collection_thumbnail(collection_id: int, session: Session = Depends(get_session)):
    """获取系列/合集的封面缩略图（优先本地 SSD 极速返回，免受 NAS 网络波动影响）"""
    col = session.get(Collection, collection_id)
    if not col:
        raise HTTPException(status_code=404, detail="Collection not found")

    # 1. 检查专属本地系列缩略图缓存
    local_col_thumb = THUMBNAILS_DIR / f"thumb_col_{collection_id}.jpg"
    if local_col_thumb.exists():
        return FileResponse(local_col_thumb, media_type="image/jpeg")

    # 2. 检查 RJ / DLsite 封面缓存
    m = RJ_PATTERN.search(col.name or "") or (RJ_PATTERN.search(col.folder_path or "") if col.folder_path else None)
    if m:
        rj_code = m.group(1).upper()
        cached_cover = COVER_CACHE_DIR / f"{rj_code}.jpg"
        if cached_cover.exists():
            try:
                shutil.copyfile(cached_cover, local_col_thumb)
            except Exception:
                pass
            return FileResponse(cached_cover, media_type="image/jpeg")

    # 3. 检查 collection.cover_asset_id 本地缩略图
    if col.cover_asset_id:
        unit_thumb = THUMBNAILS_DIR / f"thumb_{col.cover_asset_id}.jpg"
        if unit_thumb.exists():
            return FileResponse(unit_thumb, media_type="image/jpeg")

    # 4. 检查该系列下第一个音轨/视频的本地缩略图
    first_unit = session.exec(select(AssetUnit).where(AssetUnit.collection_id == col.id)).first()
    if first_unit:
        unit_thumb = THUMBNAILS_DIR / f"thumb_{first_unit.id}.jpg"
        if unit_thumb.exists():
            return FileResponse(unit_thumb, media_type="image/jpeg")

    # 5. 只有在本地 SSD 均无缓存且 NAS 在线时，才探测 NAS 目录
    if col.folder_path and is_nas_online():
        c_path = resolve_physical_path(col.folder_path)
        try:
            if c_path.exists() and c_path.is_dir():
                candidates = [c_path, c_path / "image", c_path / "图片"]
                for folder_cand in candidates:
                    if folder_cand.exists() and folder_cand.is_dir():
                        for f in folder_cand.iterdir():
                            if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
                                f_lower = f.name.lower()
                                if any(k in f_lower for k in ["cover", "封面", "jacket", "ジャケット", "main", "folder", "thumb", "poster"]):
                                    try:
                                        shutil.copyfile(f, local_col_thumb)
                                        return FileResponse(local_col_thumb, media_type="image/jpeg" if f.suffix.lower() in (".jpg", ".jpeg") else "image/png")
                                    except Exception:
                                        return FileResponse(f)
        except Exception:
            pass

    raise HTTPException(status_code=404, detail="Collection thumbnail not found")

@router.get("/subtitle/{file_id}")
def stream_subtitle(file_id: int, session: Session = Depends(get_session)):
    """将字幕/歌词文件 (SRT/VTT/LRC) 转换为浏览器原生兼容的 WebVTT 格式返回"""
    asset_file = session.get(AssetFile, file_id)
    if not asset_file:
        raise HTTPException(status_code=404, detail="Subtitle file record not found")

    is_nas = is_network_or_nas_path(asset_file.file_path)
    if is_nas and not is_nas_online():
        raise HTTPException(status_code=503, detail="NAS 存储设备暂时离线，无法获取字幕")

    path = resolve_physical_path(asset_file.file_path)
    try:
        if not path.exists():
            if is_nas:
                raise HTTPException(status_code=503, detail="NAS 存储设备暂时离线，无法获取字幕")
            raise HTTPException(status_code=404, detail="Physical subtitle file not found")
    except HTTPException:
        raise
    except (OSError, IOError, TimeoutError):
        raise HTTPException(status_code=503, detail="NAS 存储网络中断，无法获取字幕")

    try:
        # Try utf-8 first, fallback to gbk/gb2312/latin1
        content = ""
        for encoding in ("utf-8-sig", "utf-8", "gb18030", "gbk", "latin-1"):
            try:
                with open(path, "r", encoding=encoding) as f:
                    content = f.read()
                break
            except UnicodeDecodeError:
                continue

        ext = path.suffix.lower()
        if ext == ".vtt":
            vtt_content = content
        elif ext == ".lrc":
            vtt_content = lrc_to_vtt(content)
        else:
            vtt_content = srt_to_vtt(content)

        return Response(content=vtt_content, media_type="text/vtt; charset=utf-8")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse subtitle: {e}")
