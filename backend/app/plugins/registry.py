import re
import random
from typing import Dict, Any, List, Optional
from sqlmodel import Session, select, func
from app.models.entities import AssetUnit, Collection, Tag, TagClass, AssetUnitTagLink
from app.plugins.base import BaseRecommender

def natural_sort_key(title: Optional[str]):
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', title or '')]

def build_all_series_cards(session: Session, context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    聚合全库 Collection 与独立单元，生成完整的系列卡片元数据（带真实 unit_count、总时长与首轨指针）。
    """
    cols = session.exec(select(Collection)).all()
    units = session.exec(select(AssetUnit)).all()

    # Preload all unit tag links for instant (<1ms) tag metadata
    unit_tags_map = {}
    try:
        from app.services.tag_service import build_tag_hierarchy_cache
        hierarchy_cache = build_tag_hierarchy_cache(session)
        all_tag_links = session.exec(
            select(AssetUnitTagLink.unit_id, Tag, TagClass, AssetUnitTagLink.is_primary_landing)
            .join(Tag, Tag.id == AssetUnitTagLink.tag_id)
            .join(TagClass, TagClass.id == Tag.tag_class_id)
        ).all()
        for uid, tag_obj, class_obj, is_primary in all_tag_links:
            c_info = hierarchy_cache.get(tag_obj.id, {})
            unit_tags_map.setdefault(uid, []).append({
                "id": tag_obj.id,
                "name": tag_obj.name,
                "class_code": class_obj.code,
                "class_name": class_obj.display_name,
                "is_primary_landing": is_primary,
                "parent_id": tag_obj.parent_id,
                "parent_name": c_info.get("parent_name"),
                "display_path": c_info.get("display_path", tag_obj.name),
                "full_path": c_info.get("full_path", tag_obj.name),
                "ancestor_ids": c_info.get("ancestor_ids", []),
            })
    except Exception:
        pass

    col_units_map = {}
    standalone_units = []
    for u in units:
        if u.collection_id:
            col_units_map.setdefault(u.collection_id, []).append(u)
        else:
            standalone_units.append(u)

    requested_unit_type = context.get("unit_type")
    search_q = (context.get("search") or "").strip().lower()

    series_cards = []
    for c in cols:
        c_units = col_units_map.get(c.id, [])
        if not c_units:
            continue

        c_units = sorted(c_units, key=lambda x: natural_sort_key(x.title))
        first_u = c_units[0]

        has_audio = any(u.unit_type == "audio" for u in c_units)
        has_video = any(u.unit_type in ("video", "bundle") for u in c_units)
        has_image = any(u.unit_type == "image" for u in c_units)

        if has_audio and not has_video:
            ptype = "audio"
        elif has_video and not has_audio:
            ptype = "video"
        elif has_audio and has_video:
            ptype = "bundle"
        elif has_image:
            ptype = "image"
        else:
            ptype = first_u.unit_type

        # Filter by unit_type if specified
        if requested_unit_type:
            if requested_unit_type == "video" and not has_video:
                continue
            elif requested_unit_type == "audio" and not has_audio:
                continue
            elif requested_unit_type == "image" and not has_image:
                continue

        # Filter by search keyword if specified
        if search_q:
            matches_col_name = search_q in (c.name or "").lower()
            matches_any_track = any(search_q in (u.title or "").lower() for u in c_units)
            if not (matches_col_name or matches_any_track):
                continue

        # Aggregate series tags across units
        series_tags = []
        series_tag_names = set()
        seen_tag_ids = set()
        for u in c_units:
            for t in unit_tags_map.get(u.id, []):
                if t["id"] not in seen_tag_ids:
                    seen_tag_ids.add(t["id"])
                    series_tags.append(t)
                    series_tag_names.add(t["name"])

        series_cards.append({
            "id": first_u.id,
            "card_id": f"col_{c.id}",
            "title": c.name,
            "unit_type": ptype,
            "collection_id": c.id,
            "collection_name": c.name,
            "cover_file_id": first_u.cover_file_id,
            "duration_seconds": sum(u.duration_seconds or 0 for u in c_units),
            "rating": max((u.rating for u in c_units), default=0),
            "is_favorite": any(u.is_favorite for u in c_units),
            "view_count": sum(u.view_count or 0 for u in c_units),
            "total_dwell_seconds": sum(u.total_dwell_seconds or 0.0 for u in c_units),
            "created_at": c.created_at,
            "is_series": True,
            "unit_count": len(c_units),
            "representative_unit_id": first_u.id,
            "tags": series_tags,
            "tag_names": list(series_tag_names),
            "dynamic_attributes": first_u.dynamic_attributes or {},
        })

    # Also include standalone units if they match filters
    for u in standalone_units:
        if requested_unit_type:
            if requested_unit_type == "video" and u.unit_type not in ("video", "bundle"):
                continue
            elif requested_unit_type != "video" and u.unit_type != requested_unit_type:
                continue
        if search_q and search_q not in (u.title or "").lower():
            continue

        u_tags = unit_tags_map.get(u.id, [])
        u_tag_names = [t["name"] for t in u_tags]

        series_cards.append({
            "id": u.id,
            "card_id": f"unit_{u.id}",
            "title": u.title,
            "unit_type": u.unit_type,
            "collection_id": None,
            "collection_name": None,
            "cover_file_id": u.cover_file_id,
            "duration_seconds": u.duration_seconds,
            "rating": u.rating,
            "is_favorite": u.is_favorite,
            "view_count": u.view_count,
            "total_dwell_seconds": u.total_dwell_seconds,
            "created_at": u.created_at,
            "is_series": False,
            "unit_count": 1,
            "representative_unit_id": u.id,
            "tags": u_tags,
            "tag_names": u_tag_names,
            "dynamic_attributes": u.dynamic_attributes or {},
        })

    return series_cards

class DiscoverRecommender(BaseRecommender):
    name = "discover"
    display_name = "探索漫游"
    description = "随机探索媒体库，发现新鲜角落"

    def recommend(self, session: Session, context: Dict[str, Any], limit: Optional[int] = None, offset: int = 0) -> List[AssetUnit]:
        query = select(AssetUnit)
        unit_type = context.get("unit_type")
        if unit_type:
            if unit_type == "video":
                query = query.where(AssetUnit.unit_type.in_(["video", "bundle"]))
            else:
                query = query.where(AssetUnit.unit_type == unit_type)

        collection_id = context.get("collection_id")
        if collection_id:
            query = query.where(AssetUnit.collection_id == collection_id)

        search_q = context.get("search")
        if search_q:
            query = query.where(AssetUnit.title.ilike(f"%{search_q}%"))

        units = session.exec(query).all()
        if not units:
            return []
        
        shuffled = list(units)
        random.shuffle(shuffled)
        if limit and limit > 0:
            return shuffled[offset : offset + limit]
        return shuffled[offset:]

    def recommend_series(self, session: Session, context: Dict[str, Any], limit: Optional[int] = None, offset: int = 0) -> List[Dict[str, Any]]:
        cards = build_all_series_cards(session, context)
        random.shuffle(cards)
        if limit and limit > 0:
            return cards[offset : offset + limit]
        return cards[offset:]

class MemoryFlashbackRecommender(BaseRecommender):
    name = "flashback"
    display_name = "时光倒流"
    description = "优先推荐很久未回顾、或浏览次数最少的记忆"

    def recommend(self, session: Session, context: Dict[str, Any], limit: Optional[int] = None, offset: int = 0) -> List[AssetUnit]:
        query = select(AssetUnit)
        unit_type = context.get("unit_type")
        if unit_type:
            if unit_type == "video":
                query = query.where(AssetUnit.unit_type.in_(["video", "bundle"]))
            else:
                query = query.where(AssetUnit.unit_type == unit_type)

        collection_id = context.get("collection_id")
        if collection_id:
            query = query.where(AssetUnit.collection_id == collection_id)

        search_q = context.get("search")
        if search_q:
            query = query.where(AssetUnit.title.ilike(f"%{search_q}%"))

        query = query.order_by(AssetUnit.view_count.asc(), AssetUnit.created_at.asc())
        if limit and limit > 0:
            query = query.offset(offset).limit(limit)
        elif offset > 0:
            query = query.offset(offset)
        return list(session.exec(query).all())

    def recommend_series(self, session: Session, context: Dict[str, Any], limit: Optional[int] = None, offset: int = 0) -> List[Dict[str, Any]]:
        cards = build_all_series_cards(session, context)
        cards.sort(key=lambda c: (c.get("view_count", 0), c.get("created_at") or 0))
        if limit and limit > 0:
            return cards[offset : offset + limit]
        return cards[offset:]

class AffinityRecommender(BaseRecommender):
    name = "affinity"
    display_name = "猜你喜欢"
    description = "结合高评分(4~5星)、喜爱标记以及停留时长进行个性化加权"

    def recommend(self, session: Session, context: Dict[str, Any], limit: Optional[int] = None, offset: int = 0) -> List[AssetUnit]:
        query = select(AssetUnit)
        unit_type = context.get("unit_type")
        if unit_type:
            if unit_type == "video":
                query = query.where(AssetUnit.unit_type.in_(["video", "bundle"]))
            else:
                query = query.where(AssetUnit.unit_type == unit_type)

        collection_id = context.get("collection_id")
        if collection_id:
            query = query.where(AssetUnit.collection_id == collection_id)

        search_q = context.get("search")
        if search_q:
            query = query.where(AssetUnit.title.ilike(f"%{search_q}%"))

        query = query.order_by(
            AssetUnit.is_favorite.desc(),
            AssetUnit.rating.desc(),
            AssetUnit.total_dwell_seconds.desc(),
            func.random()
        )
        if limit and limit > 0:
            query = query.offset(offset).limit(limit)
        elif offset > 0:
            query = query.offset(offset)
        return list(session.exec(query).all())

    def recommend_series(self, session: Session, context: Dict[str, Any], limit: Optional[int] = None, offset: int = 0) -> List[Dict[str, Any]]:
        cards = build_all_series_cards(session, context)
        cards.sort(
            key=lambda c: (
                1 if c.get("is_favorite") else 0,
                c.get("rating", 0),
                c.get("total_dwell_seconds", 0.0),
                c.get("view_count", 0)
            ),
            reverse=True
        )
        if limit and limit > 0:
            return cards[offset : offset + limit]
        return cards[offset:]

RECOMMENDERS: Dict[str, BaseRecommender] = {
    "discover": DiscoverRecommender(),
    "flashback": MemoryFlashbackRecommender(),
    "affinity": AffinityRecommender(),
}

def get_recommender(name: str = "discover") -> BaseRecommender:
    return RECOMMENDERS.get(name, RECOMMENDERS["discover"])

def list_recommenders() -> List[Dict[str, str]]:
    return [
        {
            "id": rec.name,
            "name": rec.name,
            "display_name": rec.display_name,
            "description": rec.description
        }
        for rec in RECOMMENDERS.values()
    ]
