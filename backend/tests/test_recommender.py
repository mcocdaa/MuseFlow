import pytest
from sqlmodel import Session
from app.models.entities import AssetUnit, Collection
from app.core.db import engine, get_session
from app.plugins.registry import get_recommender, list_recommenders

@pytest.fixture(scope="module", autouse=True)
def seed_test_series_data():
    with Session(engine) as session:
        col = Collection(name="测试系列合集", folder_path="/media/test_series")
        session.add(col)
        session.commit()
        session.refresh(col)
        
        u1 = AssetUnit(title="测试第1集", unit_type="audio", collection_id=col.id)
        u2 = AssetUnit(title="测试第2集", unit_type="audio", collection_id=col.id)
        session.add(u1)
        session.add(u2)
        session.commit()


def test_registry_algorithms():
    algos = list_recommenders()
    assert len(algos) == 3
    algo_names = [a["name"] for a in algos]
    assert "discover" in algo_names
    assert "flashback" in algo_names
    assert "affinity" in algo_names

def test_recommenders_execution():
    session = next(get_session())
    for algo_id in ["discover", "flashback", "affinity"]:
        rec = get_recommender(algo_id)
        assert rec is not None
        results = rec.recommend(session, {"category": "all"})
        assert isinstance(results, list)

def test_recommenders_series_execution():
    session = next(get_session())
    for algo_id in ["discover", "flashback", "affinity"]:
        rec = get_recommender(algo_id)
        assert rec is not None
        series = rec.recommend_series(session, {"category": "all"}, limit=10)
        assert isinstance(series, list)
        if series:
            card = series[0]
            assert "title" in card
            assert "unit_count" in card
            assert "duration_seconds" in card
            assert any(c.get("is_series") is True for c in series)

def test_feed_modes():
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)

    # Test series mode
    res_series = client.get("/api/recommend/feed?mode=series&limit=10")
    assert res_series.status_code == 200
    series_data = res_series.json()
    assert isinstance(series_data, list)
    if series_data:
        assert any(item.get("is_series") is True for item in series_data)
        assert series_data[0]["unit_count"] >= 1

    # Test unit mode
    res_unit = client.get("/api/recommend/feed?mode=unit&limit=10")
    assert res_unit.status_code == 200
    unit_data = res_unit.json()
    assert isinstance(unit_data, list)
    if unit_data:
        assert unit_data[0]["is_series"] is False
        assert unit_data[0]["unit_count"] == 1
