from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
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
