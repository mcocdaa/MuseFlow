import random
from typing import Dict, Any, List, Optional, Set
from sqlmodel import Session, select
from app.models.entities import AssetUnit, TelemetryLog, AssetUnitTagLink, Collection
from app.plugins.base import BaseRecommender
from app.plugins.registry import build_all_series_cards
from app.services.preference_engine import (
    TagAffinityProfile,
    compute_unit_composite_score,
    is_unit_in_cooldown,
)

class ResonanceRecommender(BaseRecommender):
    name = "resonance"
    display_name = "灵眸共鸣"
    description = "基于多次打分复合偏好、标签亲和力扩散与疲劳度冷却的深度智能共鸣推荐"

    def recommend(
        self,
        session: Session,
        context: Dict[str, Any],
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[AssetUnit]:
        query = select(AssetUnit)
        unit_type = context.get("unit_type")
        if unit_type:
            if unit_type == "video":
                query = query.where(AssetUnit.unit_type.in_(["video", "bundle"]))
            else:
                query = query.where(AssetUnit.unit_type == unit_type)

        collection_id = context.get("collection_id")
        if collection_id:
            from app.plugins.registry import get_collection_descendants
            descendants = get_collection_descendants(session, collection_id)
            query = query.where(AssetUnit.collection_id.in_(descendants))

        search_q = context.get("search")
        if search_q:
            query = query.where(AssetUnit.title.ilike(f"%{search_q}%"))

        units = session.exec(query).all()
        if not units:
            return []

        # 1. 构建用户全局标签亲和画像
        affinity_profile = TagAffinityProfile.build_profile(session)

        # 2. 预加载标签链接与历史评分
        unit_tags_map: Dict[int, Set[int]] = {}
        for row in session.exec(select(AssetUnitTagLink.unit_id, AssetUnitTagLink.tag_id)).all():
            unit_tags_map.setdefault(row[0], set()).add(row[1])

        ratings_all = session.exec(
            select(TelemetryLog).where(TelemetryLog.action == "rate")
        ).all()
        rating_events_map = {}
        for r in ratings_all:
            rating_events_map.setdefault(r.unit_id, []).append(r)

        # 3. 计算每个候选单元的共鸣评分并排序
        scored_units = []
        for u in units:
            if is_unit_in_cooldown(u):
                continue
            u_comp = compute_unit_composite_score(
                u,
                rating_events=rating_events_map.get(u.id)
            )
            u_tags = unit_tags_map.get(u.id, set())
            resonance_score = TagAffinityProfile.calculate_resonance_score(
                u,
                u_tags,
                affinity_profile,
                unit_composite_score=u_comp
            )
            # 微量扰动防确定性死板
            jitter = random.uniform(0.0, 0.5)
            scored_units.append((resonance_score + jitter, u))

        scored_units.sort(key=lambda x: x[0], reverse=True)
        sorted_units = [item[1] for item in scored_units]

        if limit and limit > 0:
            return sorted_units[offset : offset + limit]
        return sorted_units[offset:]

    def recommend_series(
        self,
        session: Session,
        context: Dict[str, Any],
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        cards = build_all_series_cards(session, context)
        if not cards:
            return []

        affinity_profile = TagAffinityProfile.build_profile(session)

        # 预加载标签映射
        unit_tags_map: Dict[int, Set[int]] = {}
        for row in session.exec(select(AssetUnitTagLink.unit_id, AssetUnitTagLink.tag_id)).all():
            unit_tags_map.setdefault(row[0], set()).add(row[1])

        # 预加载代表单元以批量检测冷却状态
        rep_ids = [c.get("representative_unit_id") or c.get("id") for c in cards]
        rep_ids = [rid for rid in rep_ids if rid]
        rep_units_map = (
            {u.id: u for u in session.exec(select(AssetUnit).where(AssetUnit.id.in_(rep_ids))).all()}
            if rep_ids
            else {}
        )

        # 为每个系列卡片计算整体共鸣分数
        scored_cards = []
        for c in cards:
            rep_id = c.get("representative_unit_id") or c.get("id")
            rep_unit = rep_units_map.get(rep_id)
            if rep_unit and is_unit_in_cooldown(rep_unit):
                continue

            # 系列基础复合分
            rating = c.get("rating", 0)
            is_fav = bool(c.get("is_favorite"))
            dwell = c.get("total_dwell_seconds", 0.0)
            views = c.get("view_count", 0)

            explicit = (rating * 10.0) + (30.0 if is_fav else 0.0)
            implicit = (8.0 * (1.0 if views > 0 else 0.0)) + (6.0 * (1.0 if dwell > 0 else 0.0))
            col_comp = explicit + implicit

            # 系列标签亲和度
            card_tags = c.get("tags") or []
            card_tag_ids = {t["id"] for t in card_tags if "id" in t}
            tag_aff_sum = sum(affinity_profile.get(tid, 0.0) for tid in card_tag_ids)

            # 新系列发现增益 (从未点开过的作品)
            discovery_bonus = 25.0 if views == 0 and tag_aff_sum > 0 else 0.0

            series_resonance = (col_comp * 0.4) + (tag_aff_sum * 0.6) + discovery_bonus
            jitter = random.uniform(0.0, 0.5)
            c["resonance_score"] = round(series_resonance, 2)
            scored_cards.append((series_resonance + jitter, c))

        scored_cards.sort(key=lambda x: x[0], reverse=True)
        sorted_cards = [item[1] for item in scored_cards]

        if limit and limit > 0:
            return sorted_cards[offset : offset + limit]
        return sorted_cards[offset:]
