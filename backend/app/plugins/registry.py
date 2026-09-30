import random
from typing import Dict, Any, List
from sqlmodel import Session, select, func
from app.models.entities import AssetUnit
from app.plugins.base import BaseRecommender

class DiscoverRecommender(BaseRecommender):
    name = "discover"
    display_name = "探索漫游"
    description = "随机探索媒体库，发现新鲜角落"

    def recommend(self, session: Session, context: Dict[str, Any], limit: int = 20) -> List[AssetUnit]:
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

        # 获取所有匹配的候选 ID
        units = session.exec(query).all()
        if not units:
            return []
        
        # 简单高效洗牌
        shuffled = list(units)
        random.shuffle(shuffled)
        return shuffled[:limit]

class MemoryFlashbackRecommender(BaseRecommender):
    name = "flashback"
    display_name = "时光倒流"
    description = "优先推荐很久未回顾、或浏览次数最少的记忆"

    def recommend(self, session: Session, context: Dict[str, Any], limit: int = 20) -> List[AssetUnit]:
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

        # 优先选择 view_count 低且创建时间早的
        query = query.order_by(AssetUnit.view_count.asc(), AssetUnit.created_at.asc()).limit(limit * 2)
        candidates = session.exec(query).all()
        shuffled = list(candidates)
        random.shuffle(shuffled)
        return shuffled[:limit]

class AffinityRecommender(BaseRecommender):
    name = "affinity"
    display_name = "猜你喜欢"
    description = "结合高评分(4~5星)、喜爱标记以及停留时长进行个性化加权"

    def recommend(self, session: Session, context: Dict[str, Any], limit: int = 20) -> List[AssetUnit]:
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

        # 按收藏、评分降序，停留时间综合排序
        query = query.order_by(
            AssetUnit.is_favorite.desc(),
            AssetUnit.rating.desc(),
            AssetUnit.total_dwell_seconds.desc(),
            func.random()
        ).limit(limit)
        return list(session.exec(query).all())

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
            "name": rec.name,
            "display_name": rec.display_name,
            "description": rec.description
        }
        for rec in RECOMMENDERS.values()
    ]
