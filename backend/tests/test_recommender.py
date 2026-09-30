from app.plugins.registry import get_recommender, list_recommenders
from app.core.db import get_session

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
