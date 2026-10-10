import logging
import re
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, text
from sqlmodel import Session, select

from app.core.db import get_session
from app.core.taxonomy_presets import apply_taxonomy_preset, list_taxonomy_presets
from app.models.entities import AssetUnitTagLink, Tag, TagClass
from app.services.tag_service import (
    CyclicInheritanceError,
    add_tag_alias,
    assign_tag_to_unit,
    build_tag_hierarchy_cache,
    create_tag,
    delete_tag,
    get_all_tags_flat,
    get_asset_units_by_tag,
    get_descendant_tag_ids,
    get_tag_aliases,
    get_unit_tags,
    remove_tag_alias,
    remove_tag_from_unit,
    resolve_tag_by_name_or_alias,
    update_tag_parent,
)

logger = logging.getLogger("museflow.api.tags")
router = APIRouter(prefix="/api/tags", tags=["tags"])

class CreateTagRequest(BaseModel):
    name: str
    tag_class_id: int
    parent_id: Optional[int] = None
    dynamic_attributes: Optional[Dict[str, Any]] = None

class UpdateTagParentRequest(BaseModel):
    new_parent_id: Optional[int] = None

class CreateTagClassRequest(BaseModel):
    code: str
    display_name: str
    icon: Optional[str] = "tag"
    color: Optional[str] = "#6366f1"
    is_required: bool = False
    is_projectable: bool = True
    description: Optional[str] = None

class UpdateTagClassRequest(BaseModel):
    display_name: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    is_required: Optional[bool] = None
    is_projectable: Optional[bool] = None
    description: Optional[str] = None

class ApplyPresetRequest(BaseModel):
    preset_id: str

class AssignTagRequest(BaseModel):
    tag_id: int
    is_primary_landing: bool = False
    confidence: float = 1.0


@router.get("/classes")
def list_tag_classes(session: Session = Depends(get_session)):
    """获取所有支持的标签元类 (媒体形态、题材、创作者、声优、工作流等)"""
    classes = session.exec(select(TagClass)).all()
    return classes


@router.post("/classes")
def api_create_tag_class(
    req: CreateTagClassRequest, session: Session = Depends(get_session)
):
    """创建全新的永久自定义标签元类 (如项目、摄影机型、嘉宾、讲师等)"""
    code = req.code.strip().lower()
    if not code:
        raise HTTPException(status_code=400, detail="分类维度英文标识 (code) 不能为空")
    if not re.match(r"^[a-z0-9_-]+$", code):
        raise HTTPException(status_code=400, detail="code 只能包含小写字母、数字、下划线或连字符")
    if not req.display_name.strip():
        raise HTTPException(status_code=400, detail="分类维度显示名称不能为空")

    existing = session.exec(select(TagClass).where(TagClass.code == code)).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"标识为 '{code}' 的分类维度已存在")

    tc = TagClass(
        code=code,
        display_name=req.display_name.strip(),
        icon=req.icon or "tag",
        color=req.color or "#6366f1",
        is_required=req.is_required,
        is_projectable=req.is_projectable,
        description=req.description.strip() if req.description else None,
    )
    session.add(tc)
    session.commit()
    session.refresh(tc)
    return tc


@router.put("/classes/{class_id}")
def api_update_tag_class(
    class_id: int, req: UpdateTagClassRequest, session: Session = Depends(get_session)
):
    """更新标签元类属性（支持动态配置是否为必要标签族 is_required、是否可物理投影 is_projectable 等）"""
    tc = session.get(TagClass, class_id)
    if not tc:
        raise HTTPException(status_code=404, detail="标签类不存在")
    if req.display_name is not None:
        tc.display_name = req.display_name.strip()
    if req.icon is not None:
        tc.icon = req.icon
    if req.color is not None:
        tc.color = req.color
    if req.is_required is not None:
        tc.is_required = req.is_required
    if req.is_projectable is not None:
        tc.is_projectable = req.is_projectable
    if req.description is not None:
        tc.description = req.description
    session.add(tc)
    session.commit()
    session.refresh(tc)
    return tc


@router.delete("/classes/{class_id}")
def api_delete_tag_class(
    class_id: int,
    force: bool = Query(False, description="是否强制级联删除其下的所有标签和资产关联"),
    session: Session = Depends(get_session),
):
    """删除自定义标签元类（核心物理维度 media_kind 与 workflow 受保护禁止删除）"""
    tc = session.get(TagClass, class_id)
    if not tc:
        raise HTTPException(status_code=404, detail="分类维度不存在")

    # 核心物理形态与工作流受保护，禁止删除
    if tc.code in ("media_kind", "workflow"):
        raise HTTPException(
            status_code=400,
            detail=f"'{tc.display_name}' ({tc.code}) 为系统核心不变量维度，禁止删除",
        )

    # 检查维度下是否有标签
    tags = session.exec(select(Tag).where(Tag.tag_class_id == class_id)).all()
    tag_ids = [t.id for t in tags if t.id is not None]

    if tag_ids and not force:
        link_count = session.exec(
            select(func.count(AssetUnitTagLink.unit_id)).where(
                AssetUnitTagLink.tag_id.in_(tag_ids)
            )
        ).one()
        raise HTTPException(
            status_code=400,
            detail=f"维度 '{tc.display_name}' 下尚有 {len(tags)} 个标签和 {link_count} 条资产关联。如确认删除，请添加 force=true 强制级联解绑。",
        )

    if tag_ids:
        tag_ids_csv = ",".join(str(tid) for tid in tag_ids)
        session.exec(text(f"DELETE FROM asset_unit_tag_link WHERE tag_id IN ({tag_ids_csv})"))
        session.exec(text(f"DELETE FROM tag_alias WHERE tag_id IN ({tag_ids_csv})"))
        session.exec(text(f"DELETE FROM tag WHERE tag_class_id = {class_id}"))

    session.delete(tc)
    session.commit()

    from app.services.tag_service import TagHierarchyCacheManager
    TagHierarchyCacheManager.invalidate()

    return {"status": "ok", "deleted_class_id": class_id, "deleted_tags_count": len(tag_ids)}


@router.get("/presets")
def api_list_taxonomy_presets():
    """获取所有内置的领域分类体系预设模板 (音乐、播客、二次元/同人、摄影设计、技术教程)"""
    return list_taxonomy_presets()


@router.post("/presets/apply")
def api_apply_taxonomy_preset(
    req: ApplyPresetRequest, session: Session = Depends(get_session)
):
    """一键应用指定的领域分类体系预设（幂等加载，不影响已有数据）"""
    try:
        classes = apply_taxonomy_preset(session, req.preset_id)
        from app.services.tag_service import TagHierarchyCacheManager
        TagHierarchyCacheManager.invalidate()
        return {
            "status": "ok",
            "preset_id": req.preset_id,
            "classes": [
                {
                    "id": c.id,
                    "code": c.code,
                    "display_name": c.display_name,
                    "icon": c.icon,
                    "color": c.color,
                    "is_projectable": c.is_projectable,
                    "is_required": c.is_required,
                    "description": c.description,
                }
                for c in classes
            ],
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))



@router.get("/all")
def api_get_all_tags_flat(session: Session = Depends(get_session)):
    """获取全库所有标签（附带使用次数、分类信息与层级路径）"""
    return get_all_tags_flat(session)


@router.get("/tree")
def get_tag_tree(session: Session = Depends(get_session)):
    """按标签类分组获取完整的树形标签结构"""
    classes = session.exec(select(TagClass)).all()
    all_tags = session.exec(select(Tag)).all()
    cache = build_tag_hierarchy_cache(session)

    # 统计使用频次
    from collections import Counter
    links = session.exec(select(AssetUnitTagLink.tag_id)).all()
    counts = Counter(links)

    tags_by_class: Dict[int, List[Dict[str, Any]]] = {}
    for t in all_tags:
        c_info = cache.get(t.id, {})
        tags_by_class.setdefault(t.tag_class_id, []).append({
            "id": t.id,
            "name": t.name,
            "parent_id": t.parent_id,
            "parent_name": c_info.get("parent_name"),
            "display_path": c_info.get("display_path", t.name),
            "full_path": c_info.get("full_path", t.name),
            "unit_count": counts.get(t.id, 0),
            "dynamic_attributes": t.dynamic_attributes,
        })

    def build_subtree(parent_id: Optional[int], items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        nodes = []
        for it in items:
            if it["parent_id"] == parent_id:
                node = dict(it)
                node["children"] = build_subtree(it["id"], items)
                nodes.append(node)
        return nodes

    result = []
    for c in classes:
        class_items = tags_by_class.get(c.id, [])
        tree = build_subtree(None, class_items)
        result.append({
            "class_id": c.id,
            "code": c.code,
            "display_name": c.display_name,
            "icon": c.icon,
            "color": c.color,
            "tree": tree,
            "total_tags": len(class_items),
        })

    return result


@router.get("/facets/summary")
def get_facets_summary(session: Session = Depends(get_session)):
    """获取所有分面的完备度统计（已标资产数、标签总数、缺失资产数、完备度百分比）"""
    from sqlmodel import func
    from app.models.entities import AssetUnit
    total_units = session.exec(select(func.count(AssetUnit.id))).one()
    classes = session.exec(select(TagClass)).all()

    # 1. 批量统计每个 TagClass 的标签数量
    tag_count_rows = session.exec(
        select(Tag.tag_class_id, func.count(Tag.id)).group_by(Tag.tag_class_id)
    ).all()
    tag_count_map = {cid: cnt for cid, cnt in tag_count_rows}

    # 2. 批量统计每个 TagClass 的已打标资产数量
    tagged_rows = session.exec(
        select(Tag.tag_class_id, func.count(func.distinct(AssetUnitTagLink.unit_id)))
        .join(Tag, AssetUnitTagLink.tag_id == Tag.id)
        .group_by(Tag.tag_class_id)
    ).all()
    tagged_map = {cid: cnt for cid, cnt in tagged_rows}

    summary = []
    for tc in classes:
        tagged_cnt = tagged_map.get(tc.id, 0)
        tag_cnt = tag_count_map.get(tc.id, 0)
        missing = total_units - tagged_cnt
        pct = round((tagged_cnt / total_units) * 100, 1) if total_units else 0.0
        summary.append({
            "class_id": tc.id,
            "code": tc.code,
            "display_name": tc.display_name,
            "icon": tc.icon,
            "color": tc.color,
            "is_required": bool(tc.is_required),
            "is_projectable": bool(tc.is_projectable),
            "description": tc.description,
            "tag_count": tag_cnt,
            "total_units": total_units,
            "tagged_units": tagged_cnt,
            "missing_units": missing,
            "coverage_percent": pct,
        })
    return summary


@router.get("/lens/{class_code}")
def get_lens_tree(class_code: str, session: Session = Depends(get_session)):
    """
    获取指定元类的虚拟动态透镜树 (Dynamic Virtual Lens Tree)。
    返回包含直接频次与级联穿透累计频次的层级树，并包含该维度缺失资产的虚节点。
    """
    from collections import defaultdict
    from sqlmodel import func
    from app.models.entities import AssetUnit

    tc = session.exec(select(TagClass).where(TagClass.code == class_code)).first()
    if not tc:
        raise HTTPException(status_code=404, detail=f"TagClass '{class_code}' not found")

    total_units = session.exec(select(func.count(AssetUnit.id))).one()

    # 查询该类全量标签与资产映射
    tags = session.exec(select(Tag).where(Tag.tag_class_id == tc.id)).all()
    cache = build_tag_hierarchy_cache(session)

    tag_links = session.exec(
        select(AssetUnitTagLink.unit_id, AssetUnitTagLink.tag_id)
        .join(Tag, AssetUnitTagLink.tag_id == Tag.id)
        .where(Tag.tag_class_id == tc.id)
    ).all()

    units_by_tag = defaultdict(set)
    tagged_unit_ids = set()
    for uid, tid in tag_links:
        units_by_tag[tid].add(uid)
        tagged_unit_ids.add(uid)

    missing_count = total_units - len(tagged_unit_ids)

    # 预计算每个节点的子孙列表与累计资产集合
    children_map = defaultdict(list)
    for t in tags:
        if t.parent_id:
            children_map[t.parent_id].append(t.id)

    def get_all_sub_ids(tid: int) -> Set[int]:
        res = {tid}
        for ch in children_map.get(tid, []):
            res.update(get_all_sub_ids(ch))
        return res

    tag_total_units = {}
    for t in tags:
        sub_ids = get_all_sub_ids(t.id)
        all_u = set()
        for sid in sub_ids:
            all_u.update(units_by_tag[sid])
        tag_total_units[t.id] = len(all_u)

    def build_lens_subtree(parent_id: Optional[int]) -> List[Dict[str, Any]]:
        nodes = []
        for t in tags:
            if t.parent_id == parent_id:
                c_info = cache.get(t.id, {})
                child_nodes = build_lens_subtree(t.id)
                nodes.append({
                    "id": t.id,
                    "name": t.name,
                    "parent_id": t.parent_id,
                    "parent_name": c_info.get("parent_name"),
                    "display_path": c_info.get("display_path", t.name),
                    "full_path": c_info.get("full_path", t.name),
                    "direct_count": len(units_by_tag[t.id]),
                    "unit_count": tag_total_units[t.id],
                    "total_count": tag_total_units[t.id],
                    "is_unassigned": False,
                    "children": child_nodes,
                })
        nodes.sort(key=lambda x: x["unit_count"], reverse=True)
        return nodes

    tree = build_lens_subtree(None)

    unassigned_node = {
        "id": -1,
        "name": f"未分类{tc.display_name}" if tc.code == "domain" else f"未指定{tc.display_name}",
        "parent_id": None,
        "display_path": f"未归入{tc.display_name}",
        "full_path": f"未归入{tc.display_name}",
        "direct_count": missing_count,
        "unit_count": missing_count,
        "total_count": missing_count,
        "is_unassigned": True,
        "missing_facet": tc.code,
        "children": [],
    }

    return {
        "class_id": tc.id,
        "code": tc.code,
        "display_name": tc.display_name,
        "icon": tc.icon,
        "color": tc.color,
        "is_required": bool(tc.is_required),
        "is_projectable": bool(tc.is_projectable),
        "description": tc.description,
        "total_units": total_units,
        "tagged_units": len(tagged_unit_ids),
        "missing_units": missing_count,
        "coverage_percent": round((len(tagged_unit_ids) / total_units) * 100, 1) if total_units else 0.0,
        "tree": tree,
        "unassigned_node": unassigned_node,
    }


@router.post("")
@router.post("/")
def api_create_tag(req: CreateTagRequest, session: Session = Depends(get_session)):
    """创建新标签"""
    try:
        tag = create_tag(
            session=session,
            name=req.name,
            tag_class_id=req.tag_class_id,
            parent_id=req.parent_id,
            dynamic_attributes=req.dynamic_attributes,
        )
        return tag
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class UpdateTagRequest(BaseModel):
    name: Optional[str] = None
    tag_class_id: Optional[int] = None


@router.put("/{tag_id}")
def api_update_tag(
    tag_id: int, req: UpdateTagRequest, session: Session = Depends(get_session)
):
    """重命名标签或跨分类维度迁移标签（若目标维度已存在同名标签则自动无损合并并记录别名）"""
    from app.models.entities import TagAlias
    from app.services.tag_service import TagHierarchyCacheManager, normalize_tag_name

    tag = session.get(Tag, tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="标签不存在")

    target_class_id = req.tag_class_id if req.tag_class_id is not None else tag.tag_class_id
    target_name = req.name.strip() if req.name is not None and req.name.strip() else tag.name

    # 检查目标维度是否存在同名标签（若存在则执行合并）
    existing_same = session.exec(
        select(Tag).where(
            Tag.tag_class_id == target_class_id,
            Tag.name == target_name,
            Tag.id != tag_id,
        )
    ).first()

    if existing_same:
        # 迁移关联资产
        old_links = session.exec(
            select(AssetUnitTagLink).where(AssetUnitTagLink.tag_id == tag_id)
        ).all()
        target_unit_ids = set(
            session.exec(
                select(AssetUnitTagLink.unit_id).where(AssetUnitTagLink.tag_id == existing_same.id)
            ).all()
        )
        for lk in old_links:
            if lk.unit_id not in target_unit_ids:
                session.add(
                    AssetUnitTagLink(
                        unit_id=lk.unit_id,
                        tag_id=existing_same.id,
                        is_primary_landing=lk.is_primary_landing,
                        confidence=lk.confidence,
                    )
                )
                target_unit_ids.add(lk.unit_id)
            session.delete(lk)

        # 过继子标签
        children = session.exec(select(Tag).where(Tag.parent_id == tag_id)).all()
        for ch in children:
            if ch.id != existing_same.id:
                ch.parent_id = existing_same.id
                session.add(ch)

        # 若原名称不同，写入别名
        if tag.name != existing_same.name:
            has_alias = session.exec(
                select(TagAlias).where(TagAlias.tag_id == existing_same.id, TagAlias.alias_name == tag.name)
            ).first()
            if not has_alias:
                session.add(
                    TagAlias(
                        tag_id=existing_same.id,
                        alias_name=tag.name,
                        normalized_alias=tag.name.lower(),
                    )
                )

        session.flush()
        session.exec(text(f"DELETE FROM tag_alias WHERE tag_id = {tag_id}"))
        session.delete(tag)
        session.commit()
        TagHierarchyCacheManager.invalidate()
        return existing_same

    if target_class_id != tag.tag_class_id:
        tag.tag_class_id = target_class_id
        tag.parent_id = None

    if target_name != tag.name:
        old_name = tag.name
        _, base_norm = normalize_tag_name(target_name)
        scoped_norm = f"{base_norm}::{target_class_id}"
        conflict_norm = session.exec(
            select(Tag).where(Tag.normalized_name == base_norm, Tag.id != tag_id)
        ).first()
        tag.name = target_name
        tag.normalized_name = scoped_norm if conflict_norm else base_norm
        # 自动将旧名称记入别名以便后续兼容检索
        has_alias = session.exec(
            select(TagAlias).where(TagAlias.tag_id == tag.id, TagAlias.alias_name == old_name)
        ).first()
        if not has_alias:
            session.add(
                TagAlias(
                    tag_id=tag.id,
                    alias_name=old_name,
                    normalized_alias=old_name.lower(),
                )
            )

    session.add(tag)
    session.commit()
    session.refresh(tag)
    TagHierarchyCacheManager.invalidate()
    return tag


@router.put("/{tag_id}/parent")
def api_update_tag_parent(
    tag_id: int, req: UpdateTagParentRequest, session: Session = Depends(get_session)
):
    """更新标签的父级 (支持拖拽调整，自动拦截循环继承)"""
    try:
        tag = update_tag_parent(session, tag_id, req.new_parent_id)
        return tag
    except CyclicInheritanceError as e:
        raise HTTPException(status_code=400, detail=f"拓扑错误: {e}")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{tag_id}/units")
def api_get_tag_units(
    tag_id: int,
    include_descendants: bool = Query(default=True),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
):
    """查询拥有该标签 (及可选子孙标签) 的全部资产"""
    units = get_asset_units_by_tag(
        session, tag_id, include_descendants=include_descendants, limit=limit, offset=offset
    )
    return units


@router.get("/units/{unit_id}")
def api_get_unit_tags(unit_id: int, session: Session = Depends(get_session)):
    """获取指定资产的所有关联标签及物理落点锚点"""
    tags = get_unit_tags(session, unit_id)
    return tags


@router.post("/units/{unit_id}/assign")
def api_assign_tag_to_unit(
    unit_id: int, req: AssignTagRequest, session: Session = Depends(get_session)
):
    """为资产打标 (可指定是否为该类的 primary_landing 物理落点锚点)"""
    try:
        link = assign_tag_to_unit(
            session=session,
            unit_id=unit_id,
            tag_id=req.tag_id,
            is_primary_landing=req.is_primary_landing,
            confidence=req.confidence,
        )
        return {"status": "success", "link": link}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/units/{unit_id}/remove/{tag_id}")
def api_remove_tag_from_unit(
    unit_id: int, tag_id: int, session: Session = Depends(get_session)
):
    """解除资产与标签的关联"""
    success = remove_tag_from_unit(session, unit_id, tag_id)
    if not success:
        raise HTTPException(status_code=404, detail="关联不存在")
    return {"status": "success"}


@router.delete("/{tag_id}")
def api_delete_tag(tag_id: int, session: Session = Depends(get_session)):
    """删除标签并安全重平衡其子标签"""
    success = delete_tag(session, tag_id)
    if not success:
        raise HTTPException(status_code=404, detail="标签不存在")
    return {"status": "success"}


class CreateAliasRequest(BaseModel):
    alias_name: str
    language: str = "zh"
    is_preferred: bool = False


@router.get("/{tag_id}/aliases")
def api_get_tag_aliases(tag_id: int, session: Session = Depends(get_session)):
    """获取指定标签的全部同义词与多语言别名 (SKOS altLabel)"""
    return get_tag_aliases(session, tag_id)


@router.post("/{tag_id}/aliases")
def api_add_tag_alias(
    tag_id: int, req: CreateAliasRequest, session: Session = Depends(get_session)
):
    """为标签注册新别名/同义词"""
    try:
        alias = add_tag_alias(
            session=session,
            tag_id=tag_id,
            alias_name=req.alias_name,
            language=req.language,
            is_preferred=req.is_preferred,
        )
        return alias
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/aliases/{alias_id}")
def api_remove_tag_alias(alias_id: int, session: Session = Depends(get_session)):
    """删除指定的标签别名"""
    success = remove_tag_alias(session, alias_id)
    if not success:
        raise HTTPException(status_code=404, detail="别名不存在")
    return {"status": "success"}


@router.get("/concept/resolve")
def api_resolve_tag(
    term: str = Query(..., description="标签名或别名"),
    session: Session = Depends(get_session)
):
    """通过名称或别名统一归一化检索标签核心概念"""
    tag = resolve_tag_by_name_or_alias(session, term)
    if not tag:
        raise HTTPException(status_code=404, detail="未找到匹配的核心概念")
    return tag


@router.post("/reorganize")
def api_reorganize_tags(session: Session = Depends(get_session)):
    """系统性自愈与整理全量资产与合集的媒体形态标签"""
    from app.services.tag_organizer import cleanup_and_reorganize_media_kind_tags
    return cleanup_and_reorganize_media_kind_tags(session)


class BatchAssignTagRequest(BaseModel):
    unit_ids: List[int]
    tag_id: int
    is_primary_landing: bool = False
    confidence: float = 1.0


@router.post("/batch_assign")
def api_batch_assign_tag(req: BatchAssignTagRequest, session: Session = Depends(get_session)):
    """批量为多个资产单元绑定同一标签并可设为主物理落点"""
    if not req.unit_ids:
        return {"status": "success", "assigned_count": 0}
    tag = session.get(Tag, req.tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="标签不存在")

    count = 0
    for uid in req.unit_ids:
        try:
            assign_tag_to_unit(
                session=session,
                unit_id=uid,
                tag_id=req.tag_id,
                is_primary_landing=req.is_primary_landing,
                confidence=req.confidence,
            )
            count += 1
        except Exception:
            continue
    session.commit()
    return {"status": "success", "assigned_count": count}


@router.get("/suggest/{unit_id}")
def api_get_tag_suggestions(unit_id: int, session: Session = Depends(get_session)):
    """
    智能预测与推荐该资产单元待补全的多维标签：
    1. 探测其当前缺失的 TagClass (如 creator, domain, workflow)；
    2. 基于标题方括号、同编号作品共有元数据、关键词反向匹配推断高置信度候选；
    3. 返回各大类最常用的高频热门标签供一键快速补齐。
    """
    import re
    from sqlmodel import func
    from app.models.entities import AssetUnit, Collection

    unit = session.get(AssetUnit, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail=f"资产单元不存在: {unit_id}")

    # 1. 查询当前已有标签及类目
    existing_links = session.exec(
        select(AssetUnitTagLink, Tag, TagClass)
        .join(Tag, AssetUnitTagLink.tag_id == Tag.id)
        .join(TagClass, Tag.tag_class_id == TagClass.id)
        .where(AssetUnitTagLink.unit_id == unit_id)
    ).all()
    existing_class_codes = {tc.code for _, _, tc in existing_links}
    existing_tag_ids = {t.id for _, t, _ in existing_links}

    classes = session.exec(select(TagClass)).all()
    class_by_code = {c.code: c for c in classes}
    missing_classes = [c.code for c in classes if c.code not in existing_class_codes]

    # 2. 准备文本元数据
    col = session.get(Collection, unit.collection_id) if unit.collection_id else None
    col_name = col.name if col else ""
    col_path = col.folder_path if col else ""
    full_text = f"{unit.title} {col_name} {col_path}"

    suggestions = []
    seen_tag_ids = set(existing_tag_ids)

    # 2.1 标准作品编号同享推荐
    code_match = re.search(r"[A-Z]{2,4}\d{5,8}", full_text, re.I)
    if code_match:
        work_code = code_match.group(0).upper()
        # 查找带有该编号且拥有标签的其他资产
        peer_tags = session.exec(
            select(Tag, TagClass)
            .join(AssetUnitTagLink, AssetUnitTagLink.tag_id == Tag.id)
            .join(TagClass, Tag.tag_class_id == TagClass.id)
            .join(AssetUnit, AssetUnit.id == AssetUnitTagLink.unit_id)
            .where(AssetUnit.title.ilike(f"%{work_code}%"), Tag.id.not_in(seen_tag_ids))
            .limit(10)
        ).all()
        for t, tc in peer_tags:
            if t.id not in seen_tag_ids:
                seen_tag_ids.add(t.id)
                suggestions.append({
                    "tag_id": t.id,
                    "tag_name": t.name,
                    "class_code": tc.code,
                    "class_name": tc.display_name,
                    "reason": f"同编号「{work_code}」作品元数据",
                    "confidence": 0.96,
                })

    # 2.2 标题/合集名方括号与圆括号提取 [创作者/社团]
    brackets = re.findall(r"[\[\(\【\（]([^\[\]\(\)\【\】\s]{2,20})[\]\)\】\）]", f"{col_name} {unit.title}")
    for b in brackets:
        b_clean = b.strip()
        if re.match(r"^[A-Z]{0,4}\d+$", b_clean, re.I):
            continue
        matching_tag = session.exec(
            select(Tag, TagClass)
            .join(TagClass, Tag.tag_class_id == TagClass.id)
            .where(Tag.name.ilike(b_clean))
        ).first()
        if matching_tag:
            t, tc = matching_tag
            if t.id not in seen_tag_ids:
                seen_tag_ids.add(t.id)
                suggestions.append({
                    "tag_id": t.id,
                    "tag_name": t.name,
                    "class_code": tc.code,
                    "class_name": tc.display_name,
                    "reason": f"提取自标题方括号「{b_clean}」",
                    "confidence": 0.92,
                })

    # 2.3 文本命中已有标签库（抽象能力：全量探测资产所缺失的任意标签族，动态匹配已有标签）
    active_target_classes = [c for c in missing_classes]
    if active_target_classes:
        target_tags = session.exec(
            select(Tag, TagClass)
            .join(TagClass, Tag.tag_class_id == TagClass.id)
            .where(TagClass.code.in_(active_target_classes), Tag.id.not_in(seen_tag_ids))
        ).all()
        for t, tc in target_tags:
            if len(t.name) >= 2 and t.name.lower() in full_text.lower():
                if t.id not in seen_tag_ids:
                    seen_tag_ids.add(t.id)
                    suggestions.append({
                        "tag_id": t.id,
                        "tag_name": t.name,
                        "class_code": tc.code,
                        "class_name": tc.display_name,
                        "reason": f"文本命中「{t.name}」",
                        "confidence": 0.88,
                    })

    # 3. 各缺失大类的高频热门候选 (Top 8 Popular Picks per Class)
    frequent_by_class = {}
    for mc in missing_classes:
        tc = class_by_code.get(mc)
        if not tc:
            continue
        top_tags = session.exec(
            select(Tag.id, Tag.name, func.count(AssetUnitTagLink.unit_id).label("cnt"))
            .join(AssetUnitTagLink, AssetUnitTagLink.tag_id == Tag.id)
            .where(Tag.tag_class_id == tc.id, Tag.id.not_in(existing_tag_ids))
            .group_by(Tag.id)
            .order_by(func.count(AssetUnitTagLink.unit_id).desc())
            .limit(8)
        ).all()
        frequent_by_class[mc] = [
            {"id": tid, "name": tname, "unit_count": cnt}
            for tid, tname, cnt in top_tags
        ]

    missing_facets_info = [
        {
            "code": c.code,
            "display_name": c.display_name,
            "icon": c.icon,
            "color": c.color,
            "is_required": bool(c.is_required),
            "is_projectable": bool(c.is_projectable),
        }
        for c in classes if c.code in missing_classes
    ]

    return {
        "unit_id": unit_id,
        "missing_classes": missing_classes,
        "missing_facets_info": missing_facets_info,
        "suggestions": sorted(suggestions, key=lambda s: s["confidence"], reverse=True),
        "frequent_by_class": frequent_by_class,
    }
