from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select
from app.core.db import get_session
from app.models.entities import AssetFile, AssetUnit
from app.models.schemas import SystemActionRequest
from app.services.native_os import open_in_file_explorer, open_with_default_app

router = APIRouter(prefix="/api/system", tags=["system"])

def resolve_target_path(payload: SystemActionRequest, session: Session) -> str:
    if payload.path:
        return payload.path

    if payload.file_id:
        f = session.get(AssetFile, payload.file_id)
        if f:
            return f.file_path

    if payload.unit_id:
        unit = session.get(AssetUnit, payload.unit_id)
        if unit:
            f = session.exec(select(AssetFile).where(AssetFile.asset_unit_id == unit.id, AssetFile.role == "primary")).first()
            if f:
                return f.file_path
            f_any = session.exec(select(AssetFile).where(AssetFile.asset_unit_id == unit.id)).first()
            if f_any:
                return f_any.file_path

    raise HTTPException(status_code=400, detail="Cannot resolve physical path from provided parameters")

@router.post("/reveal")
def reveal_in_explorer(payload: SystemActionRequest, session: Session = Depends(get_session)):
    """在操作系统文件资源管理器中定位并选中文件"""
    path_str = resolve_target_path(payload, session)
    success = open_in_file_explorer(path_str)
    if not success:
        raise HTTPException(status_code=500, detail=f"Failed to reveal path in OS explorer: {path_str}")
    return {"status": "success", "path": path_str}

@router.post("/open")
def open_externally(payload: SystemActionRequest, session: Session = Depends(get_session)):
    """调用操作系统默认程序打开文件"""
    path_str = resolve_target_path(payload, session)
    success = open_with_default_app(path_str)
    if not success:
        raise HTTPException(status_code=500, detail=f"Failed to open with default app: {path_str}")
    return {"status": "success", "path": path_str}

class RemapPathRequest(BaseModel):
    old_prefix: str
    new_prefix: str

@router.post("/remap_path")
def remap_storage_path(payload: RemapPathRequest, session: Session = Depends(get_session)):
    r"""
    动态重映射存储路径前缀（如从 \\NAS-SERVER\media 迁移到 /mnt/nas 或新 NAS 挂载点），
    无损批量更新 AssetFile 与 Collection 路径，完好保留所有虚拟超集、收藏夹与播放历史。
    """
    old_p = payload.old_prefix.replace("\\", "/").rstrip("/")
    new_p = payload.new_prefix.replace("\\", "/").rstrip("/")

    files = session.exec(select(AssetFile)).all()
    file_count = 0
    for f in files:
        f_norm = f.file_path.replace("\\", "/")
        if f_norm.startswith(old_p):
            f.file_path = new_p + f_norm[len(old_p):]
            session.add(f)
            file_count += 1

    cols = session.exec(select(Collection)).all()
    col_count = 0
    for c in cols:
        if c.folder_path:
            c_norm = c.folder_path.replace("\\", "/")
            if c_norm.startswith(old_p):
                c.folder_path = new_p + c_norm[len(old_p):]
                session.add(c)
                col_count += 1

    session.commit()
    return {
        "status": "success",
        "remapped_files": file_count,
        "remapped_collections": col_count,
        "old_prefix": payload.old_prefix,
        "new_prefix": payload.new_prefix,
    }
