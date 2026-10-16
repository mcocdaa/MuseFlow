import re
import random
from collections import defaultdict
from typing import Dict, Any, List, Optional
from sqlmodel import Session, select, func
from app.models.entities import AssetUnit, Collection, Tag, TagClass, AssetUnitTagLink, AssetFile
from app.models.schemas import AssetFileRead
from app.plugins.base import BaseRecommender
from app.services.collection_rollup import WORK_CODE_REGEX, is_container_or_author_bucket

def get_collection_descendants(session: Session, collection_id: int) -> List[int]:
    """递归获取集合本身及其所有子孙后代集合的 ID 列表"""
    all_cols = session.exec(select(Collection.id, Collection.parent_id)).all()
    children_map = {}
    for cid, pid in all_cols:
        if pid:
            children_map.setdefault(pid, []).append(cid)
    descendants = [collection_id]
    queue = [collection_id]
    while queue:
        curr = queue.pop(0)
        for ch in children_map.get(curr, []):
            if ch not in descendants:
                descendants.append(ch)
                queue.append(ch)
    return descendants

def natural_sort_key(title: Optional[str]) -> list:
    if not title:
        return []
    parts = []
    for text in re.split(r'([0-9]+)', title):
        if not text:
            continue
        if text.isascii() and text.isdigit():
            parts.append((0, int(text)))
        else:
            parts.append((1, text.lower()))
    return parts

def build_all_series_cards(session: Session, context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    聚合全库 Collection 与独立单元，生成完整的系列卡片元数据（带真实 unit_count、总时长与首轨指针）。
    """
    cols = session.exec(select(Collection)).all()
    units = session.exec(select(AssetUnit)).all()

    # Preload all unit tag links for instant (<1ms) tag metadata using fast scalar query
    unit_tags_map = {}
    try:
        from sqlalchemy import text
        from app.services.tag_service import build_tag_hierarchy_cache
        hierarchy_cache = build_tag_hierarchy_cache(session)
        all_tags = {t.id: t for t in session.exec(select(Tag)).all()}
        all_classes = {c.id: c for c in session.exec(select(TagClass)).all()}
        tag_meta_lookup = {}
        for tid, tag_obj in all_tags.items():
            class_obj = all_classes.get(tag_obj.tag_class_id)
            c_info = hierarchy_cache.get(tag_obj.id, {})
            tag_meta_lookup[tid] = {
                "id": tag_obj.id,
                "name": tag_obj.name,
                "class_code": class_obj.code if class_obj else "tag",
                "class_name": class_obj.display_name if class_obj else "标签",
                "parent_id": tag_obj.parent_id,
                "parent_name": c_info.get("parent_name"),
                "display_path": c_info.get("display_path", tag_obj.name),
                "full_path": c_info.get("full_path", tag_obj.name),
                "ancestor_ids": c_info.get("ancestor_ids", []),
            }

        scalar_links = session.execute(
            text("SELECT unit_id, tag_id, is_primary_landing FROM asset_unit_tag_link")
        ).fetchall()
        for uid, tid, is_primary in scalar_links:
            meta = tag_meta_lookup.get(tid)
            if meta:
                tag_entry = dict(meta)
                tag_entry["is_primary_landing"] = bool(is_primary)
                unit_tags_map.setdefault(uid, []).append(tag_entry)
    except Exception:
        pass

    children_map = {}
    for c in cols:
        if c.parent_id:
            children_map.setdefault(c.parent_id, []).append(c.id)

    col_units_map = {}
    standalone_units = []
    for u in units:
        if u.collection_id:
            col_units_map.setdefault(u.collection_id, []).append(u)
        else:
            standalone_units.append(u)

    requested_unit_type = context.get("unit_type")
    search_q = (context.get("search") or "").strip().lower()
    target_collection_id = context.get("collection_id")
    target_descendants = set(get_collection_descendants(session, target_collection_id)) if target_collection_id else None

    series_cards = []
    for c in cols:
        if target_descendants is not None and c.id not in target_descendants:
            continue
        c_units = col_units_map.get(c.id, [])
        if not c_units:
            continue

        # Check if collection is an author/container bucket with loose tracks or contains atomic composite units
        has_atomic_work = any(
            (u.dynamic_attributes or {}).get("is_atomic_work") or WORK_CODE_REGEX.search(u.title or "")
            for u in c_units
        )
        is_bucket = (
            bool(children_map.get(c.id))
            or is_container_or_author_bucket(c, len(c_units))
            or has_atomic_work
        )

        if is_bucket:
            # Emit direct units in this bucket as individual work cards
            for u in c_units:
                if requested_unit_type:
                    if requested_unit_type == "video" and u.unit_type not in ("video", "bundle"):
                        continue
                    elif requested_unit_type != "video" and u.unit_type != requested_unit_type:
                        continue
                if search_q and search_q not in (u.title or "").lower() and search_q not in (c.name or "").lower():
                    continue

                u_tags = unit_tags_map.get(u.id, [])
                u_tag_names = [t["name"] for t in u_tags]
                attrs = u.dynamic_attributes or {}
                aud_cnt = int(attrs.get("audio_count") or (1 if u.unit_type == "audio" else 0))
                vid_cnt = int(attrs.get("video_count") or (1 if u.unit_type in ("video", "bundle") else 0))
                img_cnt = int(attrs.get("image_count") or (1 if u.unit_type == "image" else 0))
                trk_cnt = int(attrs.get("track_count") or max(1, aud_cnt + vid_cnt))
                tot_cnt = trk_cnt + (img_cnt if u.unit_type != "image" else 0)

                series_cards.append({
                    "id": u.id,
                    "card_id": f"unit_{u.id}",
                    "title": u.title,
                    "unit_type": u.unit_type,
                    "collection_id": c.id,
                    "collection_name": c.name,
                    "cover_file_id": u.cover_file_id,
                    "duration_seconds": u.duration_seconds,
                    "rating": float(u.rating or 0.0),
                    "composite_score": round(float(getattr(u, "composite_score", 0.0) or 0.0), 2),
                    "is_favorite": u.is_favorite,
                    "view_count": u.view_count or 0,
                    "total_dwell_seconds": u.total_dwell_seconds or 0.0,
                    "created_at": u.created_at,
                    "is_series": False,
                    "unit_count": trk_cnt,
                    "total_count": tot_cnt,
                    "audio_count": aud_cnt,
                    "video_count": vid_cnt,
                    "image_count": img_cnt,
                    "media_breakdown": {
                        "audio": aud_cnt,
                        "video": vid_cnt,
                        "image": img_cnt,
                        "total": tot_cnt,
                    },
                    "representative_unit_id": u.id,
                    "tags": u_tags,
                    "tag_names": u_tag_names,
                    "dynamic_attributes": attrs,
                })
            continue

        audio_units = [u for u in c_units if u.unit_type == "audio"]
        video_units = [u for u in c_units if u.unit_type in ("video", "bundle")]
        image_units = [u for u in c_units if u.unit_type == "image"]

        # Determine dominant primary type & representative playable tracks
        if audio_units:
            ptype = "audio"
            primary_units = audio_units
        elif video_units:
            ptype = "video"
            primary_units = video_units
        else:
            ptype = "image"
            primary_units = image_units

        # Representative unit: prioritize primary playable unit over accessory images
        sorted_primary = sorted(primary_units, key=lambda x: natural_sort_key(x.title))
        first_u = sorted_primary[0]

        # Cover resolution: if first_u has cover, use it. If not and image_units exist, use companion image as cover!
        cover_id = first_u.cover_file_id
        if not cover_id and image_units:
            for img_u in image_units:
                if img_u.cover_file_id:
                    cover_id = img_u.cover_file_id
                    break

        # Filter strictly by dominant primary type so audio/video works with internal images never leak into "image"
        if requested_unit_type:
            if requested_unit_type == "video" and ptype != "video":
                continue
            elif requested_unit_type == "audio" and ptype != "audio":
                continue
            elif requested_unit_type == "image" and ptype != "image":
                continue

        # Filter by search keyword if specified
        if search_q:
            matches_col_name = search_q in (c.name or "").lower()
            matches_any_track = any(search_q in (u.title or "").lower() for u in c_units)
            if not (matches_col_name or matches_any_track):
                continue

        # Aggregate series tags across primary units only (never pollute audio/video series with image tags)
        series_tags = []
        series_tag_names = set()
        seen_tag_ids = set()
        for u in primary_units:
            for t in unit_tags_map.get(u.id, []):
                if ptype != "image" and t.get("name") in ("图片", "独立画册"):
                    continue
                if t["id"] not in seen_tag_ids:
                    seen_tag_ids.add(t["id"])
                    series_tags.append(t)
                    series_tag_names.add(t["name"])

        # Check single-unit work vs multi-episode series
        is_single = len(primary_units) <= 1
        card_title = first_u.title if is_single else c.name
        card_id = f"unit_{first_u.id}" if is_single else f"col_{c.id}"

        series_cards.append({
            "id": first_u.id,
            "card_id": card_id,
            "title": card_title,
            "unit_type": ptype,
            "collection_id": c.id,
            "collection_name": c.name,
            "cover_file_id": cover_id,
            "duration_seconds": sum(u.duration_seconds or 0 for u in audio_units + video_units),
            "rating": max((float(u.rating or 0.0) for u in c_units), default=0.0),
            "composite_score": round(max((float(getattr(u, "composite_score", 0.0) or 0.0) for u in c_units), default=0.0), 2),
            "is_favorite": any(u.is_favorite for u in c_units),
            "view_count": sum(u.view_count or 0 for u in c_units),
            "total_dwell_seconds": sum(u.total_dwell_seconds or 0.0 for u in c_units),
            "created_at": c.created_at,
            "is_series": not is_single,
            "unit_count": len(primary_units),
            "total_count": len(c_units),
            "audio_count": len(audio_units),
            "video_count": len(video_units),
            "image_count": len(image_units),
            "media_breakdown": {
                "audio": len(audio_units),
                "video": len(video_units),
                "image": len(image_units),
                "total": len(c_units),
            },
            "representative_unit_id": first_u.id,
            "tags": series_tags,
            "tag_names": list(series_tag_names),
            "dynamic_attributes": first_u.dynamic_attributes or {},
        })

    # Also include standalone units if they match filters (only when not filtering by collection)
    if target_descendants is None:
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
            attrs = u.dynamic_attributes or {}
            aud_cnt = int(attrs.get("audio_count") or (1 if u.unit_type == "audio" else 0))
            vid_cnt = int(attrs.get("video_count") or (1 if u.unit_type in ("video", "bundle") else 0))
            img_cnt = int(attrs.get("image_count") or (1 if u.unit_type == "image" else 0))
            trk_cnt = int(attrs.get("track_count") or max(1, aud_cnt + vid_cnt))
            tot_cnt = trk_cnt + (img_cnt if u.unit_type != "image" else 0)

            series_cards.append({
                "id": u.id,
                "card_id": f"unit_{u.id}",
                "title": u.title,
                "unit_type": u.unit_type,
                "collection_id": None,
                "collection_name": None,
                "cover_file_id": u.cover_file_id,
                "duration_seconds": u.duration_seconds,
                "rating": float(u.rating or 0.0),
                "composite_score": round(float(getattr(u, "composite_score", 0.0) or 0.0), 2),
                "is_favorite": u.is_favorite,
                "view_count": u.view_count,
                "total_dwell_seconds": u.total_dwell_seconds,
                "created_at": u.created_at,
                "is_series": False,
                "unit_count": trk_cnt,
                "total_count": tot_cnt,
                "audio_count": aud_cnt,
                "video_count": vid_cnt,
                "image_count": img_cnt,
                "media_breakdown": {
                    "audio": aud_cnt,
                    "video": vid_cnt,
                    "image": img_cnt,
                    "total": tot_cnt,
                },
                "representative_unit_id": u.id,
                "tags": u_tags,
                "tag_names": u_tag_names,
                "dynamic_attributes": attrs,
            })

    # Batch preload files for all representative unit cards so front-end players can instantly stream
    all_rep_uids = [card["representative_unit_id"] for card in series_cards if card.get("representative_unit_id")]
    if all_rep_uids:
        raw_files = session.exec(select(AssetFile).where(AssetFile.asset_unit_id.in_(all_rep_uids))).all()
        files_map = defaultdict(list)
        for f in raw_files:
            files_map[f.asset_unit_id].append(AssetFileRead.model_validate(f))
        for card in series_cards:
            rep_id = card.get("representative_unit_id")
            card["files"] = files_map.get(rep_id, [])
    else:
        for card in series_cards:
            card["files"] = []

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
            descendants = get_collection_descendants(session, collection_id)
            query = query.where(AssetUnit.collection_id.in_(descendants))

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
            descendants = get_collection_descendants(session, collection_id)
            query = query.where(AssetUnit.collection_id.in_(descendants))

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
            descendants = get_collection_descendants(session, collection_id)
            query = query.where(AssetUnit.collection_id.in_(descendants))

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
    if name == "resonance":
        from app.plugins.resonance import ResonanceRecommender
        return ResonanceRecommender()
    return RECOMMENDERS.get(name, RECOMMENDERS["discover"])

def list_recommenders() -> List[Dict[str, str]]:
    from app.plugins.resonance import ResonanceRecommender
    recs = [
        DiscoverRecommender(),
        ResonanceRecommender(),
        AffinityRecommender(),
        MemoryFlashbackRecommender(),
    ]
    return [
        {
            "id": rec.name,
            "name": rec.name,
            "display_name": rec.display_name,
            "description": rec.description
        }
        for rec in recs
    ]
