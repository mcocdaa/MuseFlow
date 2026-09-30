from typing import List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session, select
from app.core.db import get_session
from app.models.entities import LibraryRoot
from app.models.schemas import ScanRequest
from app.services.scanner import scan_directory

router = APIRouter(prefix="/api/scan", tags=["scan"])

@router.post("")
def trigger_scan(payload: ScanRequest, background_tasks: BackgroundTasks, session: Session = Depends(get_session)):
    """扫描指定物理目录，建立媒体与系列索引"""
    res = scan_directory(session, payload.path)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res

@router.get("/roots", response_model=List[LibraryRoot])
def list_library_roots(session: Session = Depends(get_session)):
    return list(session.exec(select(LibraryRoot)).all())
