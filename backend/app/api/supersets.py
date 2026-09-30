from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, func
from app.core.db import get_session
from app.models.entities import Superset, SupersetUnitLink, AssetUnit
from app.models.schemas import SupersetRead

router = APIRouter(prefix="/api/supersets", tags=["supersets"])

class SupersetCreate(BaseModel):
    name: str
    description: Optional[str] = None
    icon: Optional[str] = "sparkles"

class LinkItemRequest(BaseModel):
    unit_id: int

@router.get("", response_model=List[SupersetRead])
def list_supersets(session: Session = Depends(get_session)):
    supersets = session.exec(select(Superset).order_by(Superset.created_at.desc())).all()
    results = []
    for s in supersets:
        count = session.exec(
            select(func.count()).select_from(SupersetUnitLink).where(SupersetUnitLink.superset_id == s.id)
        ).one()
        results.append(
            SupersetRead(
                id=s.id,
                name=s.name,
                description=s.description,
                icon=s.icon,
                cover_url=s.cover_url,
                unit_count=count
            )
        )
    return results

@router.post("", response_model=SupersetRead)
def create_superset(payload: SupersetCreate, session: Session = Depends(get_session)):
    s = Superset(name=payload.name, description=payload.description, icon=payload.icon)
    session.add(s)
    session.commit()
    session.refresh(s)
    return SupersetRead(
        id=s.id,
        name=s.name,
        description=s.description,
        icon=s.icon,
        cover_url=s.cover_url,
        unit_count=0
    )

@router.post("/{superset_id}/items")
def add_item_to_superset(superset_id: int, payload: LinkItemRequest, session: Session = Depends(get_session)):
    superset = session.get(Superset, superset_id)
    if not superset:
        raise HTTPException(status_code=404, detail="Superset not found")
    unit = session.get(AssetUnit, payload.unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="AssetUnit not found")

    existing = session.get(SupersetUnitLink, (superset_id, payload.unit_id))
    if not existing:
        link = SupersetUnitLink(superset_id=superset_id, unit_id=payload.unit_id)
        session.add(link)
        session.commit()
    return {"status": "success", "superset_id": superset_id, "unit_id": payload.unit_id}

@router.delete("/{superset_id}/items/{unit_id}")
def remove_item_from_superset(superset_id: int, unit_id: int, session: Session = Depends(get_session)):
    link = session.get(SupersetUnitLink, (superset_id, unit_id))
    if link:
        session.delete(link)
        session.commit()
    return {"status": "success"}
