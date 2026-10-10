import pytest
from sqlmodel import Session, select
from app.core.db import engine, init_db
from app.models.entities import AssetUnit, TagClass, Tag, AssetUnitTagLink
from app.services.tag_service import (
    create_tag,
    update_tag_parent,
    validate_no_cycle_before_add_edge,
    CyclicInheritanceError,
    get_descendant_tag_ids,
    get_ancestor_tag_ids,
    assign_tag_to_unit,
    get_asset_units_by_tag,
    get_unit_tags,
)

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    init_db()

def test_tag_classes_seeded():
    with Session(engine) as session:
        classes = session.exec(select(TagClass)).all()
        assert len(classes) >= 5
        codes = [c.code for c in classes]
        assert "domain" in codes
        assert "creator" in codes
        assert "workflow" in codes

def test_tag_creation_and_hierarchy():
    with Session(engine) as session:
        domain_cls = session.exec(select(TagClass).where(TagClass.code == "domain")).first()
        assert domain_cls is not None

        # 1. 创建根标签: 音声 (Audio)
        root_tag = create_tag(session, "同人音声_测试", domain_cls.id)
        assert root_tag.id is not None
        assert root_tag.normalized_name == "同人音声_测试"

        # 2. 创建子标签: 催眠 (Hypnosis)
        sub_tag1 = create_tag(session, "催眠_测试", domain_cls.id, parent_id=root_tag.id)
        assert sub_tag1.parent_id == root_tag.id

        # 3. 创建孙标签: 深度催眠 (Deep Hypnosis)
        sub_tag2 = create_tag(session, "深度催眠_测试", domain_cls.id, parent_id=sub_tag1.id)
        assert sub_tag2.parent_id == sub_tag1.id

        # 4. 递归 CTE 检索验证
        descendants = get_descendant_tag_ids(session, root_tag.id)
        assert root_tag.id in descendants
        assert sub_tag1.id in descendants
        assert sub_tag2.id in descendants

        # 5. 祖先继承链检索
        ancestors = get_ancestor_tag_ids(session, sub_tag2.id)
        assert ancestors == [sub_tag2.id, sub_tag1.id, root_tag.id]

def test_cycle_inheritance_prevention():
    with Session(engine) as session:
        domain_cls = session.exec(select(TagClass).where(TagClass.code == "domain")).first()

        tag_a = create_tag(session, "TagA_Test", domain_cls.id)
        tag_b = create_tag(session, "TagB_Test", domain_cls.id, parent_id=tag_a.id)
        tag_c = create_tag(session, "TagC_Test", domain_cls.id, parent_id=tag_b.id)

        # 自环检测: Tag A 不能将自身设为父节点
        with pytest.raises(CyclicInheritanceError):
            update_tag_parent(session, tag_a.id, tag_a.id)

        # 2-hop 循环检测: Tag A 将 Tag B 设为父节点 (当前 A 是 B 的父节点)
        with pytest.raises(CyclicInheritanceError):
            update_tag_parent(session, tag_a.id, tag_b.id)

        # 3-hop 循环检测: Tag A 将 Tag C 设为父节点 (当前 A -> B -> C)
        with pytest.raises(CyclicInheritanceError):
            update_tag_parent(session, tag_a.id, tag_c.id)

def test_scheme_a_primary_landing_and_unit_tagging():
    with Session(engine) as session:
        domain_cls = session.exec(select(TagClass).where(TagClass.code == "domain")).first()
        creator_cls = session.exec(select(TagClass).where(TagClass.code == "creator")).first()

        tag_sleep = create_tag(session, "助眠_Unit测试", domain_cls.id)
        tag_hypno = create_tag(session, "催眠_Unit测试", domain_cls.id)
        tag_circle = create_tag(session, "测试社团_Unit", creator_cls.id)

        # 创建一个测试资产单元
        unit = AssetUnit(title="测试ASMR作品_Unit", unit_type="audio", primary_class="VoiceDrama")
        session.add(unit)
        session.commit()
        session.refresh(unit)

        # 方案 A 验证：资产可被打上多个标签，但同一类下只有一个 is_primary_landing 物理落点
        # 1. 绑定助眠并设为物理落点
        link1 = assign_tag_to_unit(session, unit.id, tag_sleep.id, is_primary_landing=True)
        assert link1.is_primary_landing is True

        # 2. 绑定催眠为副标签 (物理落点保持助眠)
        link2 = assign_tag_to_unit(session, unit.id, tag_hypno.id, is_primary_landing=False)
        assert link2.is_primary_landing is False

        # 3. 绑定社团标签为创作者族系的物理落点
        link3 = assign_tag_to_unit(session, unit.id, tag_circle.id, is_primary_landing=True)
        assert link3.is_primary_landing is True

        # 4. 获取该单元全部标签
        tags_info = get_unit_tags(session, unit.id)
        assert len(tags_info) == 3
        landing_tags = [t for t in tags_info if t["is_primary_landing"]]
        # 两个不同类别的各有一个落点锚点 (domain: 助眠, creator: 测试社团)
        assert len(landing_tags) == 2

        # 5. 递归查询资产单元验证
        matched_units = get_asset_units_by_tag(session, tag_sleep.id, include_descendants=True)
        assert any(u.id == unit.id for u in matched_units)


def test_tag_hierarchy_cache_manager_and_invalidation():
    from app.services.tag_service import TagHierarchyCacheManager, build_tag_hierarchy_cache

    with Session(engine) as session:
        domain_cls = session.exec(select(TagClass).where(TagClass.code == "domain")).first()

        # 初始版本
        cache1 = build_tag_hierarchy_cache(session)
        v1 = TagHierarchyCacheManager._version

        # 再次获取应当直接命中内存缓存，版本不变
        cache2 = build_tag_hierarchy_cache(session)
        v2 = TagHierarchyCacheManager._version
        assert v1 == v2
        assert cache1 is cache2  # 引用完全相同

        # 创建新标签后缓存应当原子失效
        import uuid
        unique_name = f"缓存失效测试标签_{uuid.uuid4().hex[:6]}"
        new_tag = create_tag(session, unique_name, domain_cls.id)
        assert TagHierarchyCacheManager._cache is None
        assert TagHierarchyCacheManager._version > v1

        # 重新获取快照
        cache3 = build_tag_hierarchy_cache(session)
        assert new_tag.id in cache3
        assert cache3[new_tag.id]["name"] == unique_name


def test_batch_eager_loading_pipeline():
    from app.api.assets import enrich_units_batch, enrich_unit_read

    with Session(engine) as session:
        # 获取 5 个资产单元
        units = session.exec(select(AssetUnit).limit(5)).all()
        if not units:
            pytest.skip("No asset units to test")

        # 批量预加载
        batch_reads = enrich_units_batch(units, session)
        assert len(batch_reads) == len(units)

        # 单条装饰器对比一致性
        for u, b_read in zip(units, batch_reads):
            s_read = enrich_unit_read(u, session)
            assert b_read.id == s_read.id
            assert b_read.title == s_read.title
            assert len(b_read.tags) == len(s_read.tags)
            assert len(b_read.files) == len(s_read.files)


def test_tag_alias_and_concept_resolution():
    from app.services.tag_service import (
        add_tag_alias,
        get_tag_aliases,
        resolve_tag_by_name_or_alias,
        remove_tag_alias,
    )

    with Session(engine) as session:
        domain_cls = session.exec(select(TagClass).where(TagClass.code == "domain")).first()
        base_tag = create_tag(session, "同调催眠_Core", domain_cls.id)

        # 1. 注册多语言别名与首选别名
        alias_en = add_tag_alias(session, base_tag.id, "Synchro Hypnosis", language="en")
        alias_zh = add_tag_alias(session, base_tag.id, "同步催眠", language="zh", is_preferred=True)

        # 2. 列出别名
        aliases = get_tag_aliases(session, base_tag.id)
        alias_names = [a.alias_name for a in aliases]
        assert "Synchro Hypnosis" in alias_names
        assert "同步催眠" in alias_names

        # 3. 概念解析归一化 (SKOS Concept Resolution)
        res1 = resolve_tag_by_name_or_alias(session, "synchro hypnosis")
        assert res1 is not None
        assert res1.id == base_tag.id

        res2 = resolve_tag_by_name_or_alias(session, "同步催眠")
        assert res2 is not None
        assert res2.id == base_tag.id

        res3 = resolve_tag_by_name_or_alias(session, "同调催眠_Core")
        assert res3 is not None
        assert res3.id == base_tag.id

        # 4. 删除别名
        remove_tag_alias(session, alias_en.id)
        aliases_after = get_tag_aliases(session, base_tag.id)
        assert len(aliases_after) == 1
