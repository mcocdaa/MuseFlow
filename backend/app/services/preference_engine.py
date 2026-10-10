"""
MuseFlow Preference & Resonance Engine (灵眸偏好与共鸣推荐引擎)
Implements:
1. Composite Scoring: Explicit (multi-event rating, favorite) + Implicit (replay count, dwell time, loop)
2. Fatigue & Cooldown Penalty (explicit 14-day cooldown + recent overplay fatigue)
3. Tag Affinity Profiling & Propagation (hierarchical parent-child inheritance)
4. Unplayed Discovery (finding fresh gems matching user's top affinity tags)
"""

import math
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple, Set, Union
from sqlmodel import Session, select, func
from app.models.entities import AssetUnit, TelemetryLog, AssetUnitTagLink, Tag, Collection

# Decay rate per day for historical ratings
RATING_DECAY_LAMBDA = 0.03  # ~50% weight after 23 days
LOYALTY_MULTIPLIER_BASE = 0.15

def is_unit_in_cooldown(unit: AssetUnit, now_utc: Optional[datetime] = None) -> bool:
    """检查资产是否处于显式冷却池中"""
    now = now_utc or datetime.now(timezone.utc)
    attrs = unit.dynamic_attributes or {}
    cooldown_until_str = attrs.get("cooldown_until")
    if not cooldown_until_str:
        return False
    try:
        cooldown_until = datetime.fromisoformat(cooldown_until_str)
        if cooldown_until.tzinfo is None:
            cooldown_until = cooldown_until.replace(tzinfo=timezone.utc)
        return now < cooldown_until
    except Exception:
        return False

def compute_effective_rating(
    unit: AssetUnit,
    rating_events: Optional[Union[List[TelemetryLog], Session]] = None,
    now_utc: Optional[datetime] = None,
    session: Optional[Session] = None
) -> float:
    """
    计算基于多事件时序追加与时间衰减后的有效星级评分 (0.0 ~ 5.0, 保留 1 位小数)。
    每个打分事件按时间折旧加权：
      w_i = exp(-RATING_DECAY_LAMBDA * dt_days)
      R_effective = sum(w_i * score_i) / sum(w_i)
    若无历史打分事件，则返回 float(unit.rating or 0.0)。
    """
    now = now_utc or datetime.now(timezone.utc)

    actual_events: Optional[List[TelemetryLog]] = None
    if isinstance(rating_events, Session):
        session = rating_events
        actual_events = None
    elif isinstance(rating_events, list):
        actual_events = rating_events

    if actual_events is None and session is not None and getattr(unit, "id", None) is not None:
        actual_events = session.exec(
            select(TelemetryLog).where(
                TelemetryLog.unit_id == unit.id,
                TelemetryLog.action == "rate"
            )
        ).all()

    valid_ratings = [e for e in (actual_events or []) if e.action == "rate" and e.score is not None and e.score > 0]
    if not valid_ratings:
        return round(float(unit.rating or 0.0), 1)

    weighted_sum = 0.0
    weight_total = 0.0
    for r in valid_ratings:
        dt_days = max(0.0, (now - r.created_at).total_seconds() / 86400.0)
        w = math.exp(-RATING_DECAY_LAMBDA * dt_days)
        weighted_sum += float(r.score) * w
        weight_total += w

    if weight_total <= 0:
        return 0.0

    raw_rating = weighted_sum / weight_total
    return round(max(1.0, min(5.0, raw_rating)), 1)

def compute_unit_composite_score(
    unit: AssetUnit,
    rating_events: Optional[Union[List[TelemetryLog], Session]] = None,
    now_utc: Optional[datetime] = None,
    session: Optional[Session] = None
) -> float:
    """
    计算单个资产单元的综合偏好复合得分 (Composite Score):
    S_composite = (S_explicit + S_implicit) * FatigueFactor
    """
    now = now_utc or datetime.now(timezone.utc)

    # 兼容传递 session 的便捷调用
    actual_events: Optional[List[TelemetryLog]] = None
    if isinstance(rating_events, Session):
        session = rating_events
        actual_events = None
    elif isinstance(rating_events, list):
        actual_events = rating_events

    if actual_events is None and session is not None and getattr(unit, "id", None) is not None:
        actual_events = session.exec(
            select(TelemetryLog).where(TelemetryLog.unit_id == unit.id, TelemetryLog.action == "rate")
        ).all()

    # 1. 冷却池过滤：若在冷却期内，直接返回 0.0
    if is_unit_in_cooldown(unit, now):
        return 0.0

    # 2. 显式反馈得分 (Explicit Score)
    explicit_score = 0.0
    # 若有历史事件，优先使用动态衰减加权计算的有效星级
    effective_rating = compute_effective_rating(unit, rating_events=actual_events, now_utc=now, session=session)
    explicit_score += effective_rating * 10.0  # 5星 = 50分

    if unit.is_favorite:
        explicit_score += 30.0  # 收藏大加成

    # 多次打分时序累加与忠诚度加成
    if actual_events:
        valid_ratings = [e for e in actual_events if e.action == "rate" and e.score is not None]
        if valid_ratings:
            rate_history_sum = 0.0
            for r in valid_ratings:
                dt_days = max(0.0, (now - r.created_at).total_seconds() / 86400.0)
                decay_weight = math.exp(-RATING_DECAY_LAMBDA * dt_days)
                rate_history_sum += (r.score * 5.0) * decay_weight

            # 多次复评忠诚度乘数 (N次好评说明百听不厌)
            count_factor = 1.0 + LOYALTY_MULTIPLIER_BASE * min(5, len(valid_ratings) - 1)
            explicit_score += rate_history_sum * count_factor

    # 3. 隐式行为得分 (Implicit Score)
    implicit_score = 0.0
    # 对数平滑复听/复播次数收益
    view_count = unit.view_count or 0
    implicit_score += 8.0 * math.log(1.0 + view_count)

    # 有效停留时长收益
    dwell_sec = unit.total_dwell_seconds or 0.0
    implicit_score += 6.0 * math.log(1.0 + dwell_sec / 60.0)

    # 单曲循环/复读增益 (若停留时长显著超过本身音频时长，说明反复收听/循环播放)
    if unit.duration_seconds and unit.duration_seconds > 10.0:
        if dwell_sec >= unit.duration_seconds * 1.5:
            implicit_score += 15.0

    # 4. 疲劳度因子 (Fatigue Factor)
    fatigue_factor = 1.0
    # 若在最近 3 天内播放过热 (> 5 次)，给予适度饱和衰减，避免单曲霸榜
    if unit.last_viewed_at:
        last_dt_days = (now - unit.last_viewed_at).total_seconds() / 86400.0
        if last_dt_days < 3.0 and view_count >= 5:
            fatigue_factor = 0.4

    total_score = (explicit_score + implicit_score) * fatigue_factor
    return max(0.0, round(total_score, 2))

class TagAffinityProfile:
    """用户标签亲和度画像管理引擎"""

    @classmethod
    def build_profile(cls, session: Session) -> Dict[int, float]:
        """
        基于全量历史资产的复合得分，反哺并计算用户对每个标签的亲和力权重向量 (Tag Affinity Vector)
        支持面向对象层级继承传递（子标签得分向父标签渗透）。
        """
        now = datetime.now(timezone.utc)
        ratings_all = session.exec(
            select(TelemetryLog).where(TelemetryLog.action == "rate")
        ).all()
        rating_events_map = {}
        for r in ratings_all:
            rating_events_map.setdefault(r.unit_id, []).append(r)

        # 仅针对有显式评分、收藏、播放或停留的活跃单元计算
        active_unit_ids = set(rating_events_map.keys())
        active_units = session.exec(
            select(AssetUnit).where(
                (AssetUnit.rating > 0)
                | (AssetUnit.is_favorite == True)
                | (AssetUnit.view_count > 0)
                | (AssetUnit.total_dwell_seconds > 0)
            )
        ).all()
        for u in active_units:
            active_unit_ids.add(u.id)

        if not active_unit_ids:
            return {}

        units = session.exec(select(AssetUnit).where(AssetUnit.id.in_(active_unit_ids))).all()

        # 1. 计算每个单元的复合偏好分
        unit_composite_scores = {}
        for u in units:
            score = compute_unit_composite_score(
                u,
                rating_events=rating_events_map.get(u.id),
                now_utc=now
            )
            if score > 0:
                unit_composite_scores[u.id] = score

        if not unit_composite_scores:
            return {}

        # 2. 预加载所有标签链接
        links = session.exec(select(AssetUnitTagLink)).all()
        tag_scores: Dict[int, float] = {}

        for l in links:
            u_score = unit_composite_scores.get(l.unit_id, 0.0)
            if u_score > 0:
                weight = 1.0 if l.is_primary_landing else 0.7
                tag_scores[l.tag_id] = tag_scores.get(l.tag_id, 0.0) + (u_score * weight * (l.confidence or 1.0))

        # 3. 标签层级继承向上渗透 (Parent Inheritance Propagation)
        # 子标签得分按 0.4 系数反馈给父类标签 (如交响乐 -> 古典音乐 -> 音乐)
        all_tags = {t.id: t for t in session.exec(select(Tag)).all()}
        propagated_scores = dict(tag_scores)

        for tid, base_score in tag_scores.items():
            curr_tag = all_tags.get(tid)
            decay = 0.4
            while curr_tag and curr_tag.parent_id and curr_tag.parent_id in all_tags:
                pid = curr_tag.parent_id
                propagated_scores[pid] = propagated_scores.get(pid, 0.0) + (base_score * decay)
                decay *= 0.4
                curr_tag = all_tags.get(pid)

        # 归一化/取整
        return {tid: round(sc, 2) for tid, sc in propagated_scores.items() if sc > 0}

    @classmethod
    def calculate_resonance_score(
        cls,
        unit: AssetUnit,
        unit_tag_ids: Set[int],
        affinity_profile: Dict[int, float],
        unit_composite_score: float = 0.0
    ) -> float:
        """
        计算资产的共鸣推荐得分 (Resonance Score):
        - 结合资产自身的已知复合分
        - 结合该资产所带标签与用户画像的亲和度匹配得分
        - 给予「高匹配度未听冷门新作品」专门的发现增益 (Discovery Bonus)
        """
        # 冷却中直接 0 分
        if is_unit_in_cooldown(unit):
            return 0.0

        tag_affinity_sum = sum(affinity_profile.get(tid, 0.0) for tid in unit_tag_ids)

        # 探索发现增益：对于从未播放过 (view_count == 0) 的全新资产，如果标签高度契合，给予发现奖励
        discovery_bonus = 0.0
        if (unit.view_count or 0) == 0:
            if tag_affinity_sum > 0:
                discovery_bonus = 25.0 + math.log(1.0 + tag_affinity_sum) * 5.0

        # 总共鸣分 = 已知复合得分 * 0.4 + 标签画像匹配度 * 0.6 + 新探索加成
        final_score = (unit_composite_score * 0.4) + (tag_affinity_sum * 0.6) + discovery_bonus
        return round(final_score, 2)


def get_unit_score_breakdown(unit: AssetUnit, session: Session) -> Dict[str, Any]:
    """返回单个资产单元的推荐算法得分细项分解 (用于工作台算法透明度检查)"""
    now = datetime.now(timezone.utc)
    in_cooldown = is_unit_in_cooldown(unit, now)

    rating_events = session.exec(
        select(TelemetryLog).where(
            TelemetryLog.unit_id == unit.id,
            TelemetryLog.action == "rate"
        )
    ).all()

    effective_rating = compute_effective_rating(unit, rating_events=rating_events, now_utc=now)

    # 显式打分细节
    explicit_base = effective_rating * 10.0
    fav_bonus = 30.0 if unit.is_favorite else 0.0

    valid_ratings = [e for e in rating_events if e.score is not None and e.score > 0]
    rate_history_sum = 0.0
    rate_events_summary = []
    for r in valid_ratings:
        dt_days = max(0.0, (now - r.created_at).total_seconds() / 86400.0)
        decay_weight = math.exp(-RATING_DECAY_LAMBDA * dt_days)
        rate_history_sum += (r.score * 5.0) * decay_weight
        rate_events_summary.append({
            "score": r.score,
            "days_ago": round(dt_days, 1),
            "weight": round(decay_weight, 2)
        })

    loyalty_count = min(5, max(0, len(valid_ratings) - 1))
    loyalty_multiplier = 1.0 + LOYALTY_MULTIPLIER_BASE * loyalty_count
    loyalty_bonus = (rate_history_sum * (loyalty_multiplier - 1.0)) if valid_ratings else 0.0
    explicit_total = explicit_base + fav_bonus + loyalty_bonus

    # 隐式得分
    view_count = unit.view_count or 0
    view_score = round(8.0 * math.log(1.0 + view_count), 2)

    dwell_sec = unit.total_dwell_seconds or 0.0
    dwell_score = round(6.0 * math.log(1.0 + dwell_sec / 60.0), 2)

    loop_bonus = 0.0
    if unit.duration_seconds and unit.duration_seconds > 10.0 and dwell_sec >= unit.duration_seconds * 1.5:
        loop_bonus = 15.0

    implicit_total = view_score + dwell_score + loop_bonus

    # 疲劳度
    fatigue_factor = 1.0
    is_fatigued = False
    if unit.last_viewed_at:
        last_dt_days = (now - unit.last_viewed_at).total_seconds() / 86400.0
        if last_dt_days < 3.0 and view_count >= 5:
            fatigue_factor = 0.4
            is_fatigued = True

    composite_score = 0.0 if in_cooldown else round((explicit_total + implicit_total) * fatigue_factor, 2)

    return {
        "unit_id": unit.id,
        "effective_rating": effective_rating,
        "composite_score": composite_score,
        "is_in_cooldown": in_cooldown,
        "is_fatigued": is_fatigued,
        "fatigue_factor": fatigue_factor,
        "explicit": {
            "total": round(explicit_total, 2),
            "effective_rating": effective_rating,
            "base_score": round(explicit_base, 2),
            "is_favorite": unit.is_favorite,
            "favorite_bonus": fav_bonus,
            "rating_count": len(valid_ratings),
            "loyalty_multiplier": round(loyalty_multiplier, 2),
            "loyalty_bonus": round(loyalty_bonus, 2),
            "history": rate_events_summary
        },
        "implicit": {
            "total": round(implicit_total, 2),
            "view_count": view_count,
            "view_score": view_score,
            "dwell_seconds": round(dwell_sec, 1),
            "dwell_score": dwell_score,
            "loop_bonus": loop_bonus
        }
    }
