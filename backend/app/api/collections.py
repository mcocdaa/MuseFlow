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
    # Batch count units by type in a single fast query
    unit_stats = session.exec(
        select(
            AssetUnit.collection_id,
            AssetUnit.unit_type,
            func.count(AssetUnit.id)
        )
        .where(AssetUnit.collection_id != None)
        .group_by(AssetUnit.collection_id, AssetUnit.unit_type)
    ).all()

    stats_map = {}
    for cid, utype, cnt in unit_stats:
        m = stats_map.setdefault(cid, {"audio": 0, "video": 0, "image": 0, "total": 0})
        m["total"] += cnt
        if utype == "audio":
            m["audio"] += cnt
        elif utype in ("video", "bundle"):
            m["video"] += cnt
        elif utype == "image":
            m["image"] += cnt

    # Build children map for recursive rollup
    children_map = {}
    for col in collections:
        if col.parent_id:
            children_map.setdefault(col.parent_id, []).append(col.id)

    # Memoized recursive stats calculation
    memo = {}
    def get_recursive_stats(col_id):
        if col_id in memo:
            return memo[col_id]
        direct = stats_map.get(col_id, {"audio": 0, "video": 0, "image": 0, "total": 0})
        res = dict(direct)
        for child_id in children_map.get(col_id, []):
            ch_stats = get_recursive_stats(child_id)
            res["audio"] += ch_stats["audio"]
            res["video"] += ch_stats["video"]
            res["image"] += ch_stats["image"]
            res["total"] += ch_stats["total"]
        memo[col_id] = res
        return res

    result = []
    for col in collections:
        # If collection has child collections, rollup recursive counts for folder visibility
        if col.id in children_map:
            st = get_recursive_stats(col.id)
        else:
            st = stats_map.get(col.id, {"audio": 0, "video": 0, "image": 0, "total": 0})
        primary_count = st["audio"] if st["audio"] > 0 else (st["video"] if st["video"] > 0 else st["image"])
        primary_t = "audio" if st["audio"] > 0 else ("video" if st["video"] > 0 else ("image" if st["image"] > 0 else "bundle"))
        result.append(
            CollectionRead(
                id=col.id,
                name=col.name,
                folder_path=col.folder_path,
                parent_id=col.parent_id,
                description=col.description,
                cover_unit_id=col.cover_asset_id,
                primary_type=primary_t,
                unit_count=primary_count,
                total_count=st["total"],
                audio_count=st["audio"],
                video_count=st["video"],
                image_count=st["image"],
                media_breakdown=st,
                children=[]
            )
        )
    return result

@router.get("/{collection_id}", response_model=CollectionRead)
def get_collection(collection_id: int, session: Session = Depends(get_session)):
    col = session.get(Collection, collection_id)
    if not col:
        raise HTTPException(status_code=404, detail="Collection not found")
    
    from app.plugins.registry import get_collection_descendants
    descendants = get_collection_descendants(session, collection_id)

    unit_stats = session.exec(
        select(
            AssetUnit.unit_type,
            func.count(AssetUnit.id)
        )
        .where(AssetUnit.collection_id.in_(descendants))
        .group_by(AssetUnit.unit_type)
    ).all()

    st = {"audio": 0, "video": 0, "image": 0, "total": 0}
    for utype, cnt in unit_stats:
        st["total"] += cnt
        if utype == "audio":
            st["audio"] += cnt
        elif utype in ("video", "bundle"):
            st["video"] += cnt
        elif utype == "image":
            st["image"] += cnt

    primary_count = st["audio"] if st["audio"] > 0 else (st["video"] if st["video"] > 0 else st["image"])
    primary_t = "audio" if st["audio"] > 0 else ("video" if st["video"] > 0 else ("image" if st["image"] > 0 else "bundle"))

    return CollectionRead(
        id=col.id,
        name=col.name,
        folder_path=col.folder_path,
        parent_id=col.parent_id,
        description=col.description,
        cover_unit_id=col.cover_asset_id,
        primary_type=primary_t,
        unit_count=primary_count,
        total_count=st["total"],
        audio_count=st["audio"],
        video_count=st["video"],
        image_count=st["image"],
        media_breakdown=st,
        children=[]
    )
