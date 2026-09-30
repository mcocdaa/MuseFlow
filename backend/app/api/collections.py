from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, func
from app.core.db import get_session
from app.models.entities import Collection, AssetUnit
from app.models.schemas import CollectionRead

router = APIRouter(prefix="/api/collections", tags=["collections"])

@router.get("", response_model=List[CollectionRead])
def list_collections(session: Session = Depends(get_session)):
    collections = session.exec(select(Collection).order_by(Collection.name)).all()
    result = []
    for col in collections:
        count = session.exec(
            select(func.count()).select_from(AssetUnit).where(AssetUnit.collection_id == col.id)
        ).one()
        result.append(
            CollectionRead(
                id=col.id,
                name=col.name,
                folder_path=col.folder_path,
                parent_id=col.parent_id,
                description=col.description,
                cover_unit_id=col.cover_asset_id,
                unit_count=count,
                children=[]
            )
        )
    return result

@router.get("/{collection_id}", response_model=CollectionRead)
def get_collection(collection_id: int, session: Session = Depends(get_session)):
    col = session.get(Collection, collection_id)
    if not col:
        raise HTTPException(status_code=404, detail="Collection not found")
    count = session.exec(
        select(func.count()).select_from(AssetUnit).where(AssetUnit.collection_id == col.id)
    ).one()
    return CollectionRead(
        id=col.id,
        name=col.name,
        folder_path=col.folder_path,
        parent_id=col.parent_id,
        description=col.description,
        cover_unit_id=col.cover_asset_id,
        unit_count=count,
        children=[]
    )
