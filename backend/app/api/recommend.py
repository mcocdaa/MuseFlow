from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlmodel import Session
from app.core.db import get_session
from app.models.schemas import FeedCardRead
from app.api.assets import enrich_unit_read, enrich_units_batch
from app.plugins.registry import get_recommender, list_recommenders

router = APIRouter(prefix="/api/recommend", tags=["recommend"])

@router.get("/algorithms")
def get_available_algorithms():
    return list_recommenders()

@router.get("/feed", response_model=List[FeedCardRead])
def get_recommendation_feed(
    mode: str = Query("series", description="'series' (系列聚合) | 'unit' (分集平铺)"),
    algorithm: str = Query("discover", description="discover, flashback, affinity"),
    unit_type: Optional[str] = Query(None, description="image, video, audio"),
    collection_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    limit: Optional[int] = Query(None, description="返回限制数量，留空则全量返回零遗漏"),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session)
):
    recommender = get_recommender(algorithm)
    context = {
        "unit_type": unit_type,
        "collection_id": collection_id,
        "search": search,
    }
    
    if mode == "series":
        cards = recommender.recommend_series(session, context, limit=limit, offset=offset)
        return [FeedCardRead.model_validate(c) for c in cards]
    else:
        units = recommender.recommend(session, context, limit=limit, offset=offset)
        enriched_units = enrich_units_batch(units, session)
        feed_cards = []
        for ur in enriched_units:
            feed_cards.append(FeedCardRead(
                id=ur.id,
                card_id=f"unit_{ur.id}",
                title=ur.title,
                unit_type=ur.unit_type,
                collection_id=ur.collection_id,
                collection_name=ur.collection_name,
                cover_file_id=ur.cover_file_id,
                duration_seconds=ur.duration_seconds,
                width=ur.width,
                height=ur.height,
                rating=ur.rating,
                is_favorite=ur.is_favorite,
                view_count=ur.view_count,
                total_dwell_seconds=ur.total_dwell_seconds,
                last_viewed_at=ur.last_viewed_at,
                created_at=ur.created_at,
                files=ur.files,
                is_series=False,
                unit_count=1,
                representative_unit_id=ur.id,
                tags=ur.tags,
                tag_names=ur.tag_names,
                dynamic_attributes=ur.dynamic_attributes,
            ))
        return feed_cards
