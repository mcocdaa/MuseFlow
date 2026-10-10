import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.core.db import get_session
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

class AssignTagRequest(BaseModel):
    tag_id: int
    is_primary_landing: bool = False
    confidence: float = 1.0


@router.get("/classes")
def list_tag_classes(session: Session = Depends(get_session)):
    """获取所有支持的标签元类 (媒体形态、题材、创作者、声优、工作流等)"""
    classes = session.exec(select(TagClass)).all()
    return classes


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
