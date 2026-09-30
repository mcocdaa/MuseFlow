from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from app.core.db import get_session
from app.models.entities import AssetUnit, AssetFile, Collection, SupersetUnitLink
from app.models.schemas import AssetUnitRead, AssetFileRead, RateRequest

router = APIRouter(prefix="/api/assets", tags=["assets"])

def enrich_unit_read(unit: AssetUnit, session: Session) -> AssetUnitRead:
    col_name = None
    if unit.collection_id:
        col = session.get(Collection, unit.collection_id)
        if col:
            col_name = col.name

    files = session.exec(select(AssetFile).where(AssetFile.asset_unit_id == unit.id)).all()
    file_reads = [AssetFileRead.model_validate(f) for f in files]

    return AssetUnitRead(
        id=unit.id,
        title=unit.title,
        unit_type=unit.unit_type,
        collection_id=unit.collection_id,
        collection_name=col_name,
        cover_file_id=unit.cover_file_id,
        duration_seconds=unit.duration_seconds,
        width=unit.width,
        height=unit.height,
        rating=unit.rating,
        is_favorite=unit.is_favorite,
        view_count=unit.view_count,
        total_dwell_seconds=unit.total_dwell_seconds,
        last_viewed_at=unit.last_viewed_at,
        created_at=unit.created_at,
        files=file_reads,
    )

@router.get("", response_model=List[AssetUnitRead])
def list_assets(
    unit_type: Optional[str] = Query(None, description="image, video, audio, bundle"),
    collection_id: Optional[int] = Query(None),
    superset_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session)
):
    query = select(AssetUnit)

    if unit_type:
        if unit_type == "video":
            query = query.where(AssetUnit.unit_type.in_(["video", "bundle"]))
        else:
            query = query.where(AssetUnit.unit_type == unit_type)

    if collection_id is not None:
        query = query.where(AssetUnit.collection_id == collection_id)

    if superset_id is not None:
        query = query.join(SupersetUnitLink, SupersetUnitLink.unit_id == AssetUnit.id).where(
            SupersetUnitLink.superset_id == superset_id
        )

    if search:
        query = query.where(AssetUnit.title.ilike(f"%{search}%"))

    query = query.order_by(AssetUnit.created_at.desc()).offset(offset).limit(limit)
    units = session.exec(query).all()

    return [enrich_unit_read(u, session) for u in units]

@router.get("/{unit_id}", response_model=AssetUnitRead)
def get_asset(unit_id: int, session: Session = Depends(get_session)):
    unit = session.get(AssetUnit, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="AssetUnit not found")
    return enrich_unit_read(unit, session)

@router.post("/{unit_id}/rate", response_model=AssetUnitRead)
def rate_asset(unit_id: int, payload: RateRequest, session: Session = Depends(get_session)):
    unit = session.get(AssetUnit, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="AssetUnit not found")
    
    if payload.rating is not None:
        unit.rating = max(0, min(5, payload.rating))
    if payload.is_favorite is not None:
        unit.is_favorite = payload.is_favorite

    session.add(unit)
    session.commit()
    session.refresh(unit)
    return enrich_unit_read(unit, session)
