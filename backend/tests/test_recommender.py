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
        
        u1 = AssetUnit(title="测试第1集", unit_type="audio", collection_id=col.id, rating=5.0, is_favorite=True)
        u2 = AssetUnit(title="测试第2集", unit_type="audio", collection_id=col.id, rating=5.0, is_favorite=True)
        session.add(u1)
        session.add(u2)
        session.commit()


def test_registry_algorithms():
    algos = list_recommenders()
    assert len(algos) == 4
    algo_names = [a["name"] for a in algos]
    assert "discover" in algo_names
    assert "resonance" in algo_names
    assert "flashback" in algo_names
    assert "affinity" in algo_names

def test_recommenders_execution():
    session = next(get_session())
    for algo_id in ["discover", "resonance", "flashback", "affinity"]:
        rec = get_recommender(algo_id)
        assert rec is not None
        results = rec.recommend(session, {"category": "all"})
        assert isinstance(results, list)

def test_recommenders_series_execution():
    session = next(get_session())
    for algo_id in ["discover", "resonance", "flashback", "affinity"]:
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
        assert unit_data[0]["unit_count"] >= 1


def test_single_unit_collection_is_not_series():
    """验证单文件集合绝不作为多集系列输出，且以作品真实标题呈现"""
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)

    with Session(engine) as session:
        col = Collection(name="单一作者目录", folder_path="/media/single_unit_folder")
        session.add(col)
        session.commit()
        session.refresh(col)

        u = AssetUnit(title="独立单曲作品标题", unit_type="audio", collection_id=col.id)
        session.add(u)
        session.commit()
        session.refresh(u)

    res = client.get(f"/api/recommend/feed?mode=series&search={u.title}")
    assert res.status_code == 200
    cards = res.json()
    assert len(cards) >= 1
    target_card = next((c for c in cards if c["id"] == u.id), None)
    assert target_card is not None
    assert target_card["is_series"] is False
    assert target_card["unit_count"] == 1
    assert target_card["title"] == "独立单曲作品标题"


def test_recursive_collection_assets():
    """验证父级容器集合能递归查出所有子孙集合内部的资产单元"""
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)

    with Session(engine) as session:
        parent_col = Collection(name="父级大类分类", folder_path="/media/parent_cat")
        session.add(parent_col)
        session.commit()
        session.refresh(parent_col)
        pid = parent_col.id

        child_col = Collection(name="子级具体作品", folder_path="/media/parent_cat/sub_work", parent_id=pid)
        session.add(child_col)
        session.commit()
        session.refresh(child_col)

        u = AssetUnit(title="子集内部独有音轨", unit_type="audio", collection_id=child_col.id)
        session.add(u)
        session.commit()
        session.refresh(u)
        target_uid = u.id

    # 查父级集合 ID，应能查出挂在子集合下的资产
    res = client.get(f"/api/assets?collection_id={pid}")
    assert res.status_code == 200
    assets = res.json()
    asset_ids = [a["id"] for a in assets]
    assert target_uid in asset_ids


def test_recursive_collection_feed_and_endpoint():
    """验证推荐流系列聚合与单品平铺模式下，按父级集合过滤时能够递归展开且卡片具备 files 元数据"""
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)

    with Session(engine) as session:
        parent_col = Collection(name="大分类_递归测试", folder_path="/media/parent_feed_test")
        session.add(parent_col)
        session.commit()
        session.refresh(parent_col)
        pid = parent_col.id

        sub_col = Collection(name="子分类_作品集", folder_path="/media/parent_feed_test/work", parent_id=pid)
        session.add(sub_col)
        session.commit()
        session.refresh(sub_col)
        sub_col_id = sub_col.id

        u = AssetUnit(title="子集合单品音轨", unit_type="audio", collection_id=sub_col.id)
        session.add(u)
        session.commit()
        session.refresh(u)
        uid = u.id

    # 1. 验证 GET /api/collections/{pid} 能够递归统计出子集合资产
    res_col = client.get(f"/api/collections/{pid}")
    assert res_col.status_code == 200
    col_data = res_col.json()
    assert col_data["unit_count"] >= 1
    assert col_data["total_count"] >= 1

    # 2. 验证 GET /api/recommend/feed?mode=series&collection_id={pid}
    res_s = client.get(f"/api/recommend/feed?mode=series&collection_id={pid}")
    assert res_s.status_code == 200
    s_cards = res_s.json()
    assert len(s_cards) >= 1
    assert all(c["collection_id"] == sub_col_id for c in s_cards)
    # 验证卡片具有 files 列表
    assert any("files" in c for c in s_cards)

    # 3. 验证 GET /api/recommend/feed?mode=unit&collection_id={pid}
    res_u = client.get(f"/api/recommend/feed?mode=unit&collection_id={pid}")
    assert res_u.status_code == 200
    u_cards = res_u.json()
    assert len(u_cards) >= 1
    assert any(c["id"] == uid for c in u_cards)


