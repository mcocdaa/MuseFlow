import os
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse, FileResponse
from sqlmodel import Session, select
from app.core.db import get_session
from app.models.entities import AssetFile, AssetUnit
from app.services.media_processor import get_or_create_unit_thumbnail, srt_to_vtt

router = APIRouter(prefix="/api/stream", tags=["stream"])

def range_streamer(file_path: Path, start: int, end: int, chunk_size: int = 1024 * 1024):
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

@router.get("/file/{file_id}")
def stream_file(file_id: int, request: Request, session: Session = Depends(get_session)):
    """支持 HTTP 206 Range 范围请求的音视频流媒体传输"""
    asset_file = session.get(AssetFile, file_id)
    if not asset_file:
        raise HTTPException(status_code=404, detail="File record not found")

    path = Path(asset_file.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Physical file not found on disk")

    file_size = path.stat().st_size
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
    """获取该原子单元的最佳预览缩略图"""
    unit = session.get(AssetUnit, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="AssetUnit not found")

    # 优先从 primary 文件生成或读取缩略图
    primary_file = None
    if unit.cover_file_id:
        primary_file = session.get(AssetFile, unit.cover_file_id)
    if not primary_file:
        primary_file = session.exec(
            select(AssetFile).where(AssetFile.asset_unit_id == unit.id, AssetFile.role == "primary")
        ).first()

    if not primary_file:
        raise HTTPException(status_code=404, detail="No media files attached to unit")

    # If it is an image and small, can serve directly or serve generated thumb
    thumb_path = get_or_create_unit_thumbnail(unit.id, primary_file.file_path, unit.unit_type)
    if thumb_path and Path(thumb_path).exists():
        return FileResponse(thumb_path, media_type="image/jpeg")

    # Fallback to serving the original file if it exists and is an image
    orig_path = Path(primary_file.file_path)
    if orig_path.exists() and unit.unit_type == "image":
        return FileResponse(orig_path, media_type=primary_file.mime_type)

    raise HTTPException(status_code=404, detail="Thumbnail could not be generated")

@router.get("/subtitle/{file_id}")
def stream_subtitle(file_id: int, session: Session = Depends(get_session)):
    """将字幕文件转换为浏览器原生兼容的 WebVTT 格式返回"""
    asset_file = session.get(AssetFile, file_id)
    if not asset_file:
        raise HTTPException(status_code=404, detail="Subtitle file record not found")

    path = Path(asset_file.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Physical subtitle file not found")

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

        if path.suffix.lower() == ".vtt":
            vtt_content = content
        else:
            vtt_content = srt_to_vtt(content)

        return Response(content=vtt_content, media_type="text/vtt; charset=utf-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse subtitle: {e}")
