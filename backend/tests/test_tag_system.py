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
    init_db(preset="voice_drama")

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

        # 1. 创建根标签: 音乐 (Audio)
        root_tag = create_tag(session, "音乐_测试", domain_cls.id)
        assert root_tag.id is not None
        assert root_tag.normalized_name == "音乐_测试"

        # 2. 创建子标签: 古典音乐
        sub_tag1 = create_tag(session, "古典音乐_测试", domain_cls.id, parent_id=root_tag.id)
        assert sub_tag1.parent_id == root_tag.id

        # 3. 创建孙标签: 交响乐
        sub_tag2 = create_tag(session, "交响乐_测试", domain_cls.id, parent_id=sub_tag1.id)
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

        tag_rock = create_tag(session, "摇滚_Unit测试", domain_cls.id)
        tag_pop = create_tag(session, "流行_Unit测试", domain_cls.id)
        tag_circle = create_tag(session, "测试乐团_Unit", creator_cls.id)

        # 创建一个测试资产单元
        unit = AssetUnit(title="测试音乐作品_Unit", unit_type="audio", primary_class="Track")
        session.add(unit)
        session.commit()
        session.refresh(unit)

        # 方案 A 验证：资产可被打上多个标签，但同一类下只有一个 is_primary_landing 物理落点
        # 1. 绑定摇滚并设为物理落点
        link1 = assign_tag_to_unit(session, unit.id, tag_rock.id, is_primary_landing=True)
        assert link1.is_primary_landing is True

        # 2. 绑定流行为副标签 (物理落点保持摇滚)
        link2 = assign_tag_to_unit(session, unit.id, tag_pop.id, is_primary_landing=False)
        assert link2.is_primary_landing is False

        # 3. 绑定乐团标签为创作者族系的物理落点
        link3 = assign_tag_to_unit(session, unit.id, tag_circle.id, is_primary_landing=True)
        assert link3.is_primary_landing is True

        # 4. 获取该单元全部标签
        tags_info = get_unit_tags(session, unit.id)
        assert len(tags_info) == 3
        landing_tags = [t for t in tags_info if t["is_primary_landing"]]
        # 两个不同类别的各有一个落点锚点 (domain: 摇滚, creator: 测试乐团)
        assert len(landing_tags) == 2

        # 5. 递归查询资产单元验证
        matched_units = get_asset_units_by_tag(session, tag_rock.id, include_descendants=True)
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
        base_tag = create_tag(session, "交响摇滚_Core", domain_cls.id)

        # 1. 注册多语言别名与首选别名
        alias_en = add_tag_alias(session, base_tag.id, "Symphonic Rock", language="en")
        alias_zh = add_tag_alias(session, base_tag.id, "交响乐摇滚", language="zh", is_preferred=True)

        # 2. 列出别名
        aliases = get_tag_aliases(session, base_tag.id)
        alias_names = [a.alias_name for a in aliases]
        assert "Symphonic Rock" in alias_names
        assert "交响乐摇滚" in alias_names

        # 3. 概念解析归一化 (SKOS Concept Resolution)
        res1 = resolve_tag_by_name_or_alias(session, "symphonic rock")
        assert res1 is not None
        assert res1.id == base_tag.id

        res2 = resolve_tag_by_name_or_alias(session, "交响乐摇滚")
        assert res2 is not None
        assert res2.id == base_tag.id

        res3 = resolve_tag_by_name_or_alias(session, "交响摇滚_Core")
        assert res3 is not None
        assert res3.id == base_tag.id

        # 4. 删除别名
        remove_tag_alias(session, alias_en.id)
        aliases_after = get_tag_aliases(session, base_tag.id)
        assert len(aliases_after) == 1


def test_facets_summary_and_lens_tree():
    from app.api.tags import get_facets_summary, get_lens_tree
    from app.api.assets import list_assets

    with Session(engine) as session:
        # 1. 验证元类完备度统计
        summary = get_facets_summary(session)
        assert len(summary) >= 3
        codes = [s["code"] for s in summary]
        assert "domain" in codes
        assert "creator" in codes

        # 2. 验证题材虚拟透镜树
        lens_domain = get_lens_tree("domain", session)
        assert lens_domain["code"] == "domain"
        assert "tree" in lens_domain
        assert "unassigned_node" in lens_domain
        assert lens_domain["total_units"] >= 0

        # 3. 验证空洞探测接口 (missing_facet)
        missing_creators = list_assets(missing_facet="creator", limit=10, offset=0, session=session)
        assert isinstance(missing_creators, list)


def test_tag_suggestions_and_batch_assign():
    from app.api.tags import api_get_tag_suggestions, api_batch_assign_tag, BatchAssignTagRequest

    with Session(engine) as session:
        domain_cls = session.exec(select(TagClass).where(TagClass.code == "domain")).first()
        creator_cls = session.exec(select(TagClass).where(TagClass.code == "creator")).first()

        tag_cat = create_tag(session, "社团猫_Suggest", creator_cls.id)
        u1 = AssetUnit(title="[社团猫_Suggest] 测试作品01", unit_type="audio")
        u2 = AssetUnit(title="[社团猫_Suggest] 测试作品02", unit_type="audio")
        session.add(u1)
        session.add(u2)
        session.commit()
        session.refresh(u1)
        session.refresh(u2)

        # 1. 验证智能推断建议 (匹配方括号)
        sug = api_get_tag_suggestions(u1.id, session=session)
        assert "creator" in sug["missing_classes"]
        sug_names = [s["tag_name"] for s in sug["suggestions"]]
        assert "社团猫_Suggest" in sug_names

        # 2. 验证批量打标接口
        req = BatchAssignTagRequest(
            unit_ids=[u1.id, u2.id],
            tag_id=tag_cat.id,
            is_primary_landing=True
        )
        res = api_batch_assign_tag(req, session=session)
        assert res["status"] == "success"
        assert res["assigned_count"] == 2

        # 3. 验证打标后 missing_classes 消除 creator
        sug_after = api_get_tag_suggestions(u1.id, session=session)
        assert "creator" not in sug_after["missing_classes"]


def test_tag_class_required_facet_and_abstraction():
    """验证必要分面约束 (Obligatory Facet) 与抽象能力"""
    from app.api.tags import api_update_tag_class, UpdateTagClassRequest, get_facets_summary

    with Session(engine) as session:
        va_cls = session.exec(select(TagClass).where(TagClass.code == "va")).first()
        assert va_cls is not None

        # 1. 动态将 va (声优) 标记为必要标签族 is_required = True
        update_req = UpdateTagClassRequest(is_required=True, is_projectable=False)
        updated = api_update_tag_class(va_cls.id, update_req, session=session)
        assert updated.is_required is True
        assert updated.is_projectable is False

        # 2. 检查 get_facets_summary 是否携带 is_required
        summary = get_facets_summary(session)
        va_summary = next(s for s in summary if s["code"] == "va")
        assert va_summary["is_required"] is True
        assert va_summary["is_projectable"] is False

        # 3. 还原
        reset_req = UpdateTagClassRequest(is_required=False, is_projectable=True)
        reset_cls = api_update_tag_class(va_cls.id, reset_req, session=session)
        assert reset_cls.is_required is False


def test_custom_tag_class_crud_and_invariants():
    """验证用户自由创建/删除自定义永久元类，以及系统核心维度(media_kind)防误删保护"""
    from fastapi import HTTPException
    from app.api.tags import (
        api_create_tag_class,
        api_delete_tag_class,
        CreateTagClassRequest,
    )

    with Session(engine) as session:
        # 1. 创建自定义维度: 所属项目 (project)
        req = CreateTagClassRequest(
            code="custom_project",
            display_name="商业项目",
            icon="folder",
            color="#3b82f6",
            is_projectable=True,
            is_required=False,
            description="用户自建的项目维度"
        )
        created = api_create_tag_class(req, session=session)
        assert created.id is not None
        assert created.code == "custom_project"
        assert created.display_name == "商业项目"

        # 2. 在该自定义维度下创建标签
        project_tag = create_tag(session, "Project_Alpha", created.id)
        assert project_tag.tag_class_id == created.id

        # 3. 尝试直接删除该维度 (force=False 应被安全拦截，因为有标签存在)
        with pytest.raises(HTTPException) as exc_info:
            api_delete_tag_class(created.id, force=False, session=session)
        assert exc_info.value.status_code == 400
        assert "尚有" in exc_info.value.detail

        # 4. 使用 force=True 级联删除
        del_res = api_delete_tag_class(created.id, force=True, session=session)
        assert del_res["status"] == "ok"
        assert del_res["deleted_class_id"] == created.id
        assert del_res["deleted_tags_count"] == 1

        # 5. 核心维度防误删保护: 尝试删除 media_kind 应当抛出 400
        media_kind_cls = session.exec(select(TagClass).where(TagClass.code == "media_kind")).first()
        with pytest.raises(HTTPException) as exc_media:
            api_delete_tag_class(media_kind_cls.id, force=True, session=session)
        assert exc_media.value.status_code == 400
        assert "系统核心不变量" in exc_media.value.detail


def test_taxonomy_presets_api():
    """验证领域分类体系预设模板获取与一键应用"""
    from app.api.tags import (
        api_list_taxonomy_presets,
        api_apply_taxonomy_preset,
        ApplyPresetRequest,
    )

    # 1. 获取预设模板清单
    presets = api_list_taxonomy_presets()
    preset_ids = [p["id"] for p in presets]
    assert "music" in preset_ids
    assert "podcast" in preset_ids
    assert "photo_design" in preset_ids
    assert "course" in preset_ids

    # 2. 一键应用音乐预设
    with Session(engine) as session:
        apply_req = ApplyPresetRequest(preset_id="music")
        res = api_apply_taxonomy_preset(apply_req, session=session)
        assert res["status"] == "ok"
        class_codes = [c["code"] for c in res["classes"]]
        assert "artist" in class_codes
        assert "album" in class_codes
        assert "genre" in class_codes
        assert "release_year" in class_codes




