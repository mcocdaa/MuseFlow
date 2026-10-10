import pytest
from datetime import datetime, timezone, timedelta
from sqlmodel import Session, select
from fastapi.testclient import TestClient

from app.main import app
from app.core.db import engine
from app.models.entities import AssetUnit, AssetFile, TelemetryLog, Tag, TagClass, AssetUnitTagLink, Collection
from app.services.preference_engine import (
    is_unit_in_cooldown,
    compute_unit_composite_score,
    TagAffinityProfile,
)
from app.plugins.registry import get_recommender


@pytest.fixture
def test_session():
    with Session(engine) as session:
        yield session


def test_cooldown_check():
    now = datetime.now(timezone.utc)
    unit_none = AssetUnit(title="No Cooldown", unit_type="audio")
    assert not is_unit_in_cooldown(unit_none, now)

    future = (now + timedelta(days=7)).isoformat()
    unit_future = AssetUnit(title="Active Cooldown", unit_type="audio", dynamic_attributes={"cooldown_until": future})
    assert is_unit_in_cooldown(unit_future, now)

    past = (now - timedelta(days=1)).isoformat()
    unit_past = AssetUnit(title="Expired Cooldown", unit_type="audio", dynamic_attributes={"cooldown_until": past})
    assert not is_unit_in_cooldown(unit_past, now)


def test_composite_score_base_and_implicit():
    now = datetime.now(timezone.utc)
    # Unit with 5 stars, favorite, 10 views, 300 seconds dwell
    unit = AssetUnit(
        title="Favorite Masterpiece",
        unit_type="audio",
        rating=5,
        is_favorite=True,
        view_count=10,
        total_dwell_seconds=300.0,
    )
    score = compute_unit_composite_score(unit, now_utc=now)
    # Explicit: 5 * 10 = 50 + 30 (favorite) = 80
    # Implicit: 8 * ln(11) + 6 * ln(1 + 5) > 0
    assert score > 80.0

    # Cooled down unit must return 0.0
    unit.dynamic_attributes = {"cooldown_until": (now + timedelta(days=3)).isoformat()}
    assert compute_unit_composite_score(unit, now_utc=now) == 0.0


def test_multi_event_rating_loyalty():
    now = datetime.now(timezone.utc)
    unit = AssetUnit(title="Loyal Unit", unit_type="audio", rating=5)

    # Single rating event today
    events_1 = [
        TelemetryLog(unit_id=1, action="rate", score=5.0, created_at=now)
    ]
    score_1 = compute_unit_composite_score(unit, rating_events=events_1, now_utc=now)

    # 3 repeated 5-star ratings (demonstrating sustained replay enthusiasm)
    events_3 = [
        TelemetryLog(unit_id=1, action="rate", score=5.0, created_at=now),
        TelemetryLog(unit_id=1, action="rate", score=5.0, created_at=now - timedelta(days=2)),
        TelemetryLog(unit_id=1, action="rate", score=5.0, created_at=now - timedelta(days=5)),
    ]
    score_3 = compute_unit_composite_score(unit, rating_events=events_3, now_utc=now)

    # Repeated ratings must reinforce score via loyalty factor
    assert score_3 > score_1


def test_tag_affinity_propagation_and_resonance(test_session: Session):
    # Setup test TagClass and hierarchical Tags:
    # 题材流派 (domain) -> 音乐 (root) -> 古典音乐 (child) -> 交响乐 (grandchild)
    t_class = TagClass(code="test_domain", display_name="测试流派")
    test_session.add(t_class)
    test_session.commit()
    test_session.refresh(t_class)

    t_root = Tag(name="测试音乐根", normalized_name="测试音乐根", tag_class_id=t_class.id)
    test_session.add(t_root)
    test_session.commit()
    test_session.refresh(t_root)

    t_child = Tag(name="测试古典音乐", normalized_name="测试古典音乐", tag_class_id=t_class.id, parent_id=t_root.id)
    test_session.add(t_child)
    test_session.commit()
    test_session.refresh(t_child)

    t_grand = Tag(name="测试交响乐", normalized_name="测试交响乐", tag_class_id=t_class.id, parent_id=t_child.id)
    test_session.add(t_grand)
    test_session.commit()
    test_session.refresh(t_grand)

    # Create a unit tagged with grandchild
    u1 = AssetUnit(title="高分交响神作", unit_type="audio", rating=5, is_favorite=True)
    test_session.add(u1)
    test_session.commit()
    test_session.refresh(u1)

    link = AssetUnitTagLink(unit_id=u1.id, tag_id=t_grand.id, is_primary_landing=False)
    test_session.add(link)
    test_session.commit()

    # Build profile
    profile = TagAffinityProfile.build_profile(test_session)
    assert t_grand.id in profile
    # Grandparent and parent must receive propagated affinity
    assert t_child.id in profile
    assert t_root.id in profile
    assert profile[t_child.id] > 0
    assert profile[t_root.id] > 0

    # Unplayed candidate unit with matching tag should get discovery bonus
    u_fresh = AssetUnit(title="未听过的音乐新品", unit_type="audio", view_count=0, rating=0)
    score_fresh = TagAffinityProfile.calculate_resonance_score(
        u_fresh,
        unit_tag_ids={t_grand.id},
        affinity_profile=profile,
        unit_composite_score=0.0
    )
    # Must be boosted by unplayed discovery bonus
    assert score_fresh > 0


def test_api_rate_and_cooldown_integration(test_session: Session):
    client = TestClient(app)

    # Create test unit
    unit = AssetUnit(title="API测试音频", unit_type="audio", rating=0)
    test_session.add(unit)
    test_session.commit()
    test_session.refresh(unit)

    # 1. Rate asset via API
    res_rate = client.post(f"/api/assets/{unit.id}/rate", json={"rating": 5, "notes": "极品好物"})
    assert res_rate.status_code == 200
    assert res_rate.json()["rating"] == 5

    # Verify telemetry log recorded
    logs = test_session.exec(select(TelemetryLog).where(TelemetryLog.unit_id == unit.id, TelemetryLog.action == "rate")).all()
    assert len(logs) >= 1
    assert logs[0].score == 5.0
    assert logs[0].context_metadata.get("notes") == "极品好物"

    # 2. Cooldown asset via API
    res_cool = client.post(f"/api/assets/{unit.id}/cooldown", json={"days": 14, "reason": "暂时听腻"})
    assert res_cool.status_code == 200
    assert "cooldown_until" in res_cool.json()["dynamic_attributes"]

    test_session.refresh(unit)
    assert is_unit_in_cooldown(unit)

    # 3. Test Resonance recommender execution excludes cooled-down units
    recommender = get_recommender("resonance")
    assert recommender is not None
    feed = recommender.recommend(test_session, {"category": "all"})
    feed_ids = [u.id for u in feed]
    assert unit.id not in feed_ids


def test_repeated_rating_decimals_and_stats(test_session: Session):
    client = TestClient(app)

    unit = AssetUnit(title="多次打分测试音频", unit_type="audio", rating=0.0)
    test_session.add(unit)
    test_session.commit()
    test_session.refresh(unit)

    # 1st rating: 3
    r1 = client.post(f"/api/assets/{unit.id}/rate", json={"rating": 3})
    assert r1.status_code == 200
    assert r1.json()["rating"] == 3.0

    # 2nd rating: 4 -> average is (3 + 4) / 2 = 3.5
    r2 = client.post(f"/api/assets/{unit.id}/rate", json={"rating": 4})
    assert r2.status_code == 200
    assert r2.json()["rating"] == 3.5

    # 3rd rating: 3 -> average is (3 + 4 + 3) / 3 = 3.3
    r3 = client.post(f"/api/assets/{unit.id}/rate", json={"rating": 3})
    assert r3.status_code == 200
    assert r3.json()["rating"] == 3.3

    # 4th rating: 4 -> average is (3 + 4 + 3 + 4) / 4 = 3.5
    r4 = client.post(f"/api/assets/{unit.id}/rate", json={"rating": 4})
    assert r4.status_code == 200
    assert r4.json()["rating"] == 3.5

    # 5th rating: 5 -> average is (3 + 4 + 3 + 4 + 5) / 5 = 3.8
    r5 = client.post(f"/api/assets/{unit.id}/rate", json={"rating": 5})
    assert r5.status_code == 200
    assert r5.json()["rating"] == 3.8

    # Query algorithm stats breakdown
    stats_res = client.get(f"/api/assets/{unit.id}/algorithm_stats")
    assert stats_res.status_code == 200
    data = stats_res.json()
    assert data["effective_rating"] == 3.8
    assert data["explicit"]["rating_count"] == 5
    assert data["explicit"]["loyalty_multiplier"] > 1.0
    assert data["composite_score"] > 0.0
