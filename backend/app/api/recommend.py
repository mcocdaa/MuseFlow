from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select
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
            attrs = ur.dynamic_attributes or {}
            aud_cnt = int(attrs.get("audio_count") or (1 if ur.unit_type == "audio" else 0))
            vid_cnt = int(attrs.get("video_count") or (1 if ur.unit_type in ("video", "bundle") else 0))
            img_cnt = int(attrs.get("image_count") or (1 if ur.unit_type == "image" else 0))
            trk_cnt = int(attrs.get("track_count") or max(1, aud_cnt + vid_cnt))
            tot_cnt = trk_cnt + (img_cnt if ur.unit_type != "image" else 0)
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
                composite_score=ur.composite_score,
                resonance_score=ur.resonance_score,
                is_favorite=ur.is_favorite,
                view_count=ur.view_count,
                total_dwell_seconds=ur.total_dwell_seconds,
                last_viewed_at=ur.last_viewed_at,
                created_at=ur.created_at,
                files=ur.files,
                is_series=False,
                unit_count=trk_cnt,
                total_count=tot_cnt,
                audio_count=aud_cnt,
                video_count=vid_cnt,
                image_count=img_cnt,
                media_breakdown={
                    "audio": aud_cnt,
                    "video": vid_cnt,
                    "image": img_cnt,
                    "total": tot_cnt,
                },
                representative_unit_id=ur.id,
                tags=ur.tags,
                tag_names=ur.tag_names,
                dynamic_attributes=attrs,
            ))
        return feed_cards

@router.get("/profile/tags")
def get_user_tag_affinity_profile(
    limit: int = 20,
    session: Session = Depends(get_session)
):
    """获取用户当前的标签亲和度画像向量与偏好排行"""
    from app.services.preference_engine import TagAffinityProfile
    from app.models.entities import Tag, TagClass

    affinity_vector = TagAffinityProfile.build_profile(session)
    if not affinity_vector:
        return []

    all_tags = {t.id: t for t in session.exec(select(Tag)).all()}
    all_classes = {c.id: c for c in session.exec(select(TagClass)).all()}

    sorted_tags = sorted(affinity_vector.items(), key=lambda x: x[1], reverse=True)[:limit]
    result = []
    for tid, score in sorted_tags:
        tag_obj = all_tags.get(tid)
        if tag_obj:
            c_obj = all_classes.get(tag_obj.tag_class_id)
            result.append({
                "tag_id": tid,
                "name": tag_obj.name,
                "class_code": c_obj.code if c_obj else "unknown",
                "class_name": c_obj.display_name if c_obj else "标签",
                "affinity_score": score
            })
    return result
