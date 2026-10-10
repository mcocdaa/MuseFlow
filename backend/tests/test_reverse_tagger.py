import pytest
from sqlmodel import Session, select
from app.core.db import engine, init_db
from app.models.entities import AssetUnit, Tag, TagClass, AssetUnitTagLink
from app.services.reverse_tagger import (
    infer_and_assign_tags_from_path,
    cleanup_dirty_tags,
    get_or_create_tag_fast,
)
from app.services.tag_service import get_unit_tags

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    init_db()

def test_reverse_tag_inference():
    with Session(engine) as session:
        unit = AssetUnit(title="[TechWave] 架构设计演进 01", unit_type="bundle")
        session.add(unit)
        session.commit()
        session.refresh(unit)

        sample_path = "/mnt/media/Audio/Podcasts/Technology/[TechWave] 架构设计演进 01/track.flac"
        library_root = "/mnt/media"

        assigned = infer_and_assign_tags_from_path(session, unit, sample_path, library_root)
        
        # 验证推断出的标签元类正交性
        classes_inferred = {a["class"] for a in assigned}
        assert "media_kind" in classes_inferred
        assert "domain" in classes_inferred
        assert "creator" in classes_inferred

        # 验证创作者提取
        creators = [a["name"] for a in assigned if a["class"] == "creator"]
        assert "TechWave" in creators

        # 验证落点锚点
        tags_info = get_unit_tags(session, unit.id)
        landing_tags = [t for t in tags_info if t["is_primary_landing"]]
        assert len(landing_tags) >= 1


def test_cleanup_dirty_tags_and_primary_landing_dedup():
    with Session(engine) as session:
        classes = session.exec(select(TagClass)).all()
        class_map = {c.code: c.id for c in classes}
        tag_by_norm = {t.normalized_name: t for t in session.exec(select(Tag)).all()}

        # 1. 创建测试系统脏标签 (盘符、系统段、纯符号)
        mnt_tag = get_or_create_tag_fast(session, tag_by_norm, "mnt", class_map["domain"])
        drive_tag = get_or_create_tag_fast(session, tag_by_norm, "D:", class_map["domain"])
        punct_tag = get_or_create_tag_fast(session, tag_by_norm, "---", class_map["domain"])

        # 2. 创建测试单元与父子落点冲突
        dom_parent = get_or_create_tag_fast(session, tag_by_norm, "音乐", class_map["domain"])
        dom_child = get_or_create_tag_fast(session, tag_by_norm, "古典", class_map["domain"], parent_id=dom_parent.id)

        test_u = AssetUnit(title="测试通用落点单元", unit_type="audio")
        session.add(test_u)
        session.commit()
        session.refresh(test_u)

        # 故意同时挂载父标签与子标签为 primary landing
        link_p = AssetUnitTagLink(unit_id=test_u.id, tag_id=dom_parent.id, is_primary_landing=True)
        link_c = AssetUnitTagLink(unit_id=test_u.id, tag_id=dom_child.id, is_primary_landing=True)
        link_mnt = AssetUnitTagLink(unit_id=test_u.id, tag_id=mnt_tag.id, is_primary_landing=False)
        link_drive = AssetUnitTagLink(unit_id=test_u.id, tag_id=drive_tag.id, is_primary_landing=False)
        link_punct = AssetUnitTagLink(unit_id=test_u.id, tag_id=punct_tag.id, is_primary_landing=False)
        session.add_all([link_p, link_c, link_mnt, link_drive, link_punct])
        session.commit()

        mnt_tag_id = mnt_tag.id
        drive_tag_id = drive_tag.id
        punct_tag_id = punct_tag.id

        # 3. 执行自愈清洗
        cleaned = cleanup_dirty_tags(session, tag_by_norm, class_map)
        session.commit()

        # 验证系统级脏标签被清理
        assert session.get(Tag, mnt_tag_id) is None
        assert session.get(Tag, drive_tag_id) is None
        assert session.get(Tag, punct_tag_id) is None

        # 验证方案 A 物理落点锚点唯一性：父标签降级为 0，最具体的子标签保留为 1
        refreshed_p = session.exec(
            select(AssetUnitTagLink).where(AssetUnitTagLink.unit_id == test_u.id, AssetUnitTagLink.tag_id == dom_parent.id)
        ).first()
        refreshed_c = session.exec(
            select(AssetUnitTagLink).where(AssetUnitTagLink.unit_id == test_u.id, AssetUnitTagLink.tag_id == dom_child.id)
        ).first()
        assert refreshed_p.is_primary_landing is False
        assert refreshed_c.is_primary_landing is True
