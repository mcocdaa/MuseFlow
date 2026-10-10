from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == "MuseFlow"
    assert data["version"] == "0.1.0"

def test_recommend_algorithms():
    response = client.get("/api/recommend/algorithms")
    assert response.status_code == 200
    algos = response.json()
    assert len(algos) >= 3
    ids = [a["id"] for a in algos]
    assert "discover" in ids
    assert "flashback" in ids
    assert "affinity" in ids

def test_ai_settings():
    response = client.get("/api/ai/settings")
    assert response.status_code == 200
    data = response.json()
    assert "model" in data
    assert "has_api_key" in data

def test_collections_list():
    response = client.get("/api/collections")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_supersets_list():
    response = client.get("/api/supersets")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_create_superset_from_queue():
    # Test creating a superset atomically from a queue
    payload = {
        "name": "测试队列另存为超集",
        "description": "单元测试生成的虚拟超集",
        "icon": "music",
        "unit_ids": []
    }
    response = client.post("/api/supersets/from_queue", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "测试队列另存为超集"
    assert data["unit_count"] == 0
    assert "id" in data

    superset_id = data["id"]
    # Test batch items link
    batch_res = client.post(f"/api/supersets/{superset_id}/items_batch", json={"unit_ids": []})
    assert batch_res.status_code == 200

    # Test delete superset
    del_res = client.delete(f"/api/supersets/{superset_id}")
    assert del_res.status_code == 200
    assert del_res.json()["deleted_id"] == superset_id


