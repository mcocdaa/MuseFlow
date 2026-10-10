import pytest
from sqlmodel import Session, select
from app.core.db import engine, init_db
from app.models.entities import AssetUnit, Tag, TagClass
from app.services.reverse_tagger import infer_and_assign_tags_from_path
from app.services.tag_service import get_unit_tags

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    init_db()

def test_reverse_tag_inference():
    with Session(engine) as session:
        unit = AssetUnit(title="甜蜜耳语测试", unit_type="bundle")
        session.add(unit)
        session.commit()
        session.refresh(unit)

        sample_path = "/mnt/z/mcoc/音声/助眠/待翻译/[RJ390418] 甜蜜耳语/track.wav"
        library_root = "/mnt/z/mcoc"

        assigned = infer_and_assign_tags_from_path(session, unit, sample_path, library_root)
        
        # 验证推断出的标签
        classes_inferred = [a["class"] for a in assigned]
        assert "media_kind" in classes_inferred
        assert "domain" in classes_inferred
        assert "workflow" in classes_inferred

        # 验证单元属性推导
        session.refresh(unit)
        assert unit.primary_class == "VoiceDrama"
        assert unit.dynamic_attributes.get("rj_code") == "RJ390418"
        assert unit.dynamic_attributes.get("has_translation") is False

        # 验证落点锚点
        tags_info = get_unit_tags(session, unit.id)
        landing_tags = [t for t in tags_info if t["is_primary_landing"]]
        assert len(landing_tags) >= 2 # media_kind, domain, workflow
