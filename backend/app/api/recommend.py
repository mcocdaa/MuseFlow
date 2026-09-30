from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlmodel import Session
from app.core.db import get_session
from app.models.schemas import AssetUnitRead
from app.api.assets import enrich_unit_read
from app.plugins.registry import get_recommender, list_recommenders

router = APIRouter(prefix="/api/recommend", tags=["recommend"])

@router.get("/algorithms")
def get_available_algorithms():
    return list_recommenders()

@router.get("/feed", response_model=List[AssetUnitRead])
def get_recommendation_feed(
    algorithm: str = Query("discover", description="discover, flashback, affinity"),
    unit_type: Optional[str] = Query(None, description="image, video, audio"),
    collection_id: Optional[int] = Query(None),
    limit: int = Query(24, le=100),
    session: Session = Depends(get_session)
):
    recommender = get_recommender(algorithm)
    context = {
        "unit_type": unit_type,
        "collection_id": collection_id,
    }
    units = recommender.recommend(session, context, limit=limit)
    return [enrich_unit_read(u, session) for u in units]
