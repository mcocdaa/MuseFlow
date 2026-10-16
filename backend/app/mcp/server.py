"""
MuseFlow MCP (Model Context Protocol) Server — External AI Plugin Hub
面向外部通用 Coding Agent (Claude Desktop, Cursor, Antigravity, AEFlow, OpenCode 等) 提供的标准 MCP 插件服务。
MuseFlow 核心保持纯粹与零内置 LLM 耦合，所有深度 AI 语义分析与整理（标签列重构、同义词合并、树形上下位归纳、混乱系列拆分、复合包配对）
均通过本 MCP 协议作为外部 Agent 插件执行。
"""

import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
from sqlmodel import Session, select, func
from sqlalchemy import text

# 确保 app 能够正确引入
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from mcp.server.mcpserver import MCPServer
from app.core.db import engine
from app.models.entities import (
    AssetUnit,
    AssetFile,
    Collection,
    Tag,
    TagClass,
    TagAlias,
    AssetUnitTagLink,
    TelemetryLog,
)
from app.services.tag_service import (
    normalize_tag_name,
    TagHierarchyCacheManager,
    update_tag_parent,
    delete_tag,
    add_tag_alias,
)
from app.services.preference_engine import is_unit_in_cooldown
from app.services.ai_organizer import gather_folder_file_tree, apply_ai_triage_plan
from app.api.tags import get_tag_tree, api_update_tag, UpdateTagRequest

mcp = MCPServer("museflow")


@mcp.tool()
def get_library_stats() -> Dict[str, Any]:
    """获取当前媒体库总体统计数据，包括资产单元数、物理文件数、合集数、标签数及健康状态"""
    with Session(engine) as session:
        units_count = session.exec(select(func.count(AssetUnit.id))).one()
        files_count = session.exec(select(func.count(AssetFile.id))).one()
        cols_count = session.exec(select(func.count(Collection.id))).one()
        tags_count = session.exec(select(func.count(Tag.id))).one()
        links_count = session.exec(select(func.count(AssetUnitTagLink.unit_id))).one()

        broken_primary = session.execute(
            text(
                "SELECT asset_unit_id, COUNT(*) FROM assetfile WHERE role = 'primary' GROUP BY asset_unit_id HAVING COUNT(*) != 1"
            )
        ).fetchall()

        return {
            "total_asset_units": units_count,
            "total_asset_files": files_count,
            "total_collections": cols_count,
            "total_tags": tags_count,
            "total_tag_links": links_count,
            "primary_invariant_violations": len(broken_primary),
            "status": "healthy" if len(broken_primary) == 0 else "needs_healing",
        }


@mcp.tool()
def get_taxonomy_tree(class_code: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    获取多维分类与标签树（支持按 class_code 筛选特定标签列，如 'domain', 'creator', 'va', 'character'）。
    返回每个标签的层级树、关联作品数 (unit_count) 与同义词别名 (aliases)，供外部 AI 深入分析并规整该列。
    """
    with Session(engine) as session:
        tree_data = get_tag_tree(session)
        cache = TagHierarchyCacheManager.get_cache(session)

        def enrich_aliases(nodes: List[Dict[str, Any]]) -> None:
            for n in nodes:
                c_info = cache.get(n["id"], {})
                n["aliases"] = c_info.get("aliases", [])
                if n.get("children"):
                    enrich_aliases(n["children"])

        results = []
        for dim in tree_data:
            if class_code and dim["code"] != class_code:
                continue
            enrich_aliases(dim.get("tree", []))
            results.append(dim)
        return results


@mcp.tool()
def organize_tag_column(class_code: str, operations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    由外部 AI Agent 对指定分类维度列 (class_code) 执行批量深度治理与重构。
    operations 列表中每项支持以下动作 (op)：
    - {"op": "create", "name": "新标签名", "parent_name": "可选父标签名"}
    - {"op": "rename_or_merge", "tag_id": 12, "new_name": "标准名称"} (若目标名称已存在则自动无损合并资产关联、子标签与别名)
    - {"op": "reparent", "tag_id": 12, "parent_id": 5, "parent_name": "可选父标签名"} (设置上下位继承树，传 null 设为顶级标签)
    - {"op": "move_class", "tag_id": 12, "target_class_code": "creator"} (跨分类维度迁移标签)
    - {"op": "add_alias", "tag_id": 12, "aliases": ["同义词1", "外文名2"]} (绑定多语言/同义词别名)
    - {"op": "delete", "tag_id": 12} (删除杂质标签，子标签自动上移保留)
    """
    with Session(engine) as session:
        tc = session.exec(select(TagClass).where(TagClass.code == class_code)).first()
        if not tc:
            return {"error": f"TagClass '{class_code}' not found"}

        applied = 0
        errors = []

        for idx, item in enumerate(operations):
            op = item.get("op")
            try:
                if op == "create":
                    name = (item.get("name") or "").strip()
                    if not name:
                        continue
                    parent_id = item.get("parent_id")
                    parent_name = (item.get("parent_name") or "").strip()
                    if not parent_id and parent_name:
                        p_tag = session.exec(
                            select(Tag).where(Tag.tag_class_id == tc.id, Tag.name == parent_name)
                        ).first()
                        if p_tag:
                            parent_id = p_tag.id
                    _, norm_name = normalize_tag_name(name)
                    existing = session.exec(
                        select(Tag).where(Tag.tag_class_id == tc.id, Tag.name == name)
                    ).first()
                    if not existing:
                        scoped_norm = f"{norm_name}::{tc.id}"
                        conflict = session.exec(select(Tag).where(Tag.normalized_name == norm_name)).first()
                        new_t = Tag(
                            name=name,
                            normalized_name=scoped_norm if conflict else norm_name,
                            tag_class_id=tc.id,
                            parent_id=parent_id,
                        )
                        session.add(new_t)
                        session.commit()
                    applied += 1

                elif op == "rename_or_merge":
                    tag_id = int(item["tag_id"])
                    new_name = (item.get("new_name") or "").strip()
                    if new_name:
                        api_update_tag(tag_id, UpdateTagRequest(name=new_name), session)
                        applied += 1

                elif op == "reparent":
                    tag_id = int(item["tag_id"])
                    new_parent_id = item.get("parent_id")
                    parent_name = (item.get("parent_name") or "").strip()
                    if new_parent_id is None and parent_name:
                        p_tag = session.exec(
                            select(Tag).where(Tag.tag_class_id == tc.id, Tag.name == parent_name)
                        ).first()
                        if p_tag:
                            new_parent_id = p_tag.id
                    update_tag_parent(session, tag_id, new_parent_id)
                    applied += 1

                elif op == "move_class":
                    tag_id = int(item["tag_id"])
                    target_code = (item.get("target_class_code") or "").strip()
                    target_tc = session.exec(select(TagClass).where(TagClass.code == target_code)).first()
                    if target_tc:
                        api_update_tag(tag_id, UpdateTagRequest(tag_class_id=target_tc.id), session)
                        applied += 1

                elif op == "add_alias":
                    tag_id = int(item["tag_id"])
                    aliases = item.get("aliases") or []
                    if isinstance(aliases, str):
                        aliases = [aliases]
                    for al in aliases:
                        al_clean = al.strip()
                        if al_clean:
                            add_tag_alias(session, tag_id, al_clean)
                    applied += 1

                elif op == "delete":
                    tag_id = int(item["tag_id"])
                    delete_tag(session, tag_id)
                    applied += 1
            except Exception as e:
                errors.append({"index": idx, "op": op, "error": str(e)})

        TagHierarchyCacheManager.invalidate()
        return {
            "status": "ok",
            "class_code": class_code,
            "applied_operations": applied,
            "errors": errors,
        }


@mcp.tool()
def analyze_collection_topology(
    collection_id: Optional[int] = None,
    folder_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    导出指定系列合集 (collection_id) 或物理目录 (folder_path) 的完整拓扑结构、子合集、单元与物理文件树，
    供外部 AI Agent 深入分析嵌套子系列拆分或跨目录音画字幕复合包配对。
    """
    with Session(engine) as session:
        col = session.get(Collection, collection_id) if collection_id else None
        if not col and folder_path:
            col = session.exec(select(Collection).where(Collection.folder_path == folder_path)).first()

        target_folder = col.folder_path if (col and col.folder_path) else folder_path
        disk_files = []
        if target_folder and Path(target_folder).exists():
            disk_files = gather_folder_file_tree(Path(target_folder))

        child_cols = []
        units_data = []
        if col:
            children = session.exec(select(Collection).where(Collection.parent_id == col.id)).all()
            child_cols = [{"id": c.id, "name": c.name, "folder_path": c.folder_path} for c in children]

            units = session.exec(select(AssetUnit).where(AssetUnit.collection_id == col.id)).all()
            for u in units:
                files = session.exec(select(AssetFile).where(AssetFile.asset_unit_id == u.id)).all()
                tags = session.exec(
                    select(Tag.name)
                    .join(AssetUnitTagLink, AssetUnitTagLink.tag_id == Tag.id)
                    .where(AssetUnitTagLink.unit_id == u.id)
                ).all()
                units_data.append({
                    "id": u.id,
                    "title": u.title,
                    "unit_type": u.unit_type,
                    "tags": list(tags),
                    "files": [
                        {
                            "id": f.id,
                            "file_name": f.file_name,
                            "file_path": f.file_path,
                            "role": f.role,
                            "extension": f.extension,
                        }
                        for f in files
                    ],
                })

        return {
            "collection": {
                "id": col.id,
                "name": col.name,
                "folder_path": col.folder_path,
                "parent_id": col.parent_id,
            } if col else None,
            "child_collections": child_cols,
            "indexed_units": units_data,
            "physical_file_tree": disk_files,
        }


@mcp.tool()
def restructure_collection_series(folder_path: str, plan: Dict[str, Any]) -> Dict[str, Any]:
    """
    将外部 AI Agent 生成的系列拆分与复合包重组方案 (plan) 无损应用至数据库（不修改或破坏任何底层磁盘物理文件）。
    plan 结构包含 collections 列表（每个含 name, folder_rel_path, units: [{title, unit_type, primary_file, auxiliary_files}]）
    及可选的 recommended_supersets。
    """
    with Session(engine) as session:
        return apply_ai_triage_plan(session, folder_path, plan)


@mcp.tool()
def search_assets(
    query: str = "",
    unit_type: Optional[str] = None,
    collection_id: Optional[int] = None,
    limit: int = 20,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """全文搜索资产单元，支持按类型 (audio/video/image/bundle)、所属合集或关键词过滤"""
    with Session(engine) as session:
        stmt = select(AssetUnit)
        if query:
            stmt = stmt.where(AssetUnit.title.ilike(f"%{query}%"))
        if unit_type and unit_type != "all":
            if unit_type == "video":
                stmt = stmt.where(AssetUnit.unit_type.in_(["video", "bundle"]))
            else:
                stmt = stmt.where(AssetUnit.unit_type == unit_type)
        if collection_id is not None:
            stmt = stmt.where(AssetUnit.collection_id == collection_id)

        units = session.exec(stmt.order_by(AssetUnit.id.desc()).offset(offset).limit(limit)).all()
        result = []
        for u in units:
            tags = session.exec(
                select(Tag.name)
                .join(AssetUnitTagLink, AssetUnitTagLink.tag_id == Tag.id)
                .where(AssetUnitTagLink.unit_id == u.id)
            ).all()
            primary_file = session.exec(
                select(AssetFile).where(AssetFile.asset_unit_id == u.id, AssetFile.role == "primary")
            ).first()

            result.append({
                "id": u.id,
                "title": u.title,
                "unit_type": u.unit_type,
                "rating": u.rating,
                "is_favorite": u.is_favorite,
                "view_count": u.view_count,
                "tags": list(tags),
                "primary_path": primary_file.file_path if primary_file else None,
                "is_cooled_down": is_unit_in_cooldown(u),
            })
        return result


@mcp.tool()
def get_asset_details(unit_id: int) -> Dict[str, Any]:
    """获取单个资产单元的详尽信息，包括所有挂载文件 (主文件、字幕、音轨)、关联标签和动态属性"""
    with Session(engine) as session:
        unit = session.get(AssetUnit, unit_id)
        if not unit:
            return {"error": f"AssetUnit with id {unit_id} not found"}

        files = session.exec(select(AssetFile).where(AssetFile.asset_unit_id == unit_id)).all()
        tag_rows = session.exec(
            select(Tag, AssetUnitTagLink)
            .join(AssetUnitTagLink, AssetUnitTagLink.tag_id == Tag.id)
            .where(AssetUnitTagLink.unit_id == unit_id)
        ).all()

        col = session.get(Collection, unit.collection_id) if unit.collection_id else None

        return {
            "id": unit.id,
            "title": unit.title,
            "unit_type": unit.unit_type,
            "collection_id": unit.collection_id,
            "collection_name": col.name if col else None,
            "rating": unit.rating,
            "is_favorite": unit.is_favorite,
            "view_count": unit.view_count,
            "total_dwell_seconds": unit.total_dwell_seconds,
            "dynamic_attributes": unit.dynamic_attributes or {},
            "files": [
                {
                    "id": f.id,
                    "file_name": f.file_name,
                    "file_path": f.file_path,
                    "extension": f.extension,
                    "mime_type": f.mime_type,
                    "file_size": f.file_size,
                    "role": f.role,
                    "duration_seconds": getattr(f, "duration_seconds", None),
                }
                for f in files
            ],
            "tags": [
                {
                    "id": t.id,
                    "name": t.name,
                    "is_primary_landing": link.is_primary_landing,
                    "confidence": link.confidence,
                }
                for t, link in tag_rows
            ],
        }


@mcp.tool()
def get_untagged_assets(limit: int = 50) -> List[Dict[str, Any]]:
    """查找尚未打标或缺少创作者/流派标签的资产，便于外部 Agent 自动识别并打标治理"""
    with Session(engine) as session:
        stmt = (
            select(AssetUnit, func.count(AssetUnitTagLink.unit_id).label("tag_count"))
            .outerjoin(AssetUnitTagLink, AssetUnitTagLink.unit_id == AssetUnit.id)
            .group_by(AssetUnit.id)
            .having(func.count(AssetUnitTagLink.unit_id) < 2)
            .limit(limit)
        )
        rows = session.exec(stmt).all()
        results = []
        for u, tag_cnt in rows:
            primary_file = session.exec(
                select(AssetFile).where(AssetFile.asset_unit_id == u.id, AssetFile.role == "primary")
            ).first()
            results.append({
                "id": u.id,
                "title": u.title,
                "unit_type": u.unit_type,
                "current_tag_count": tag_cnt,
                "primary_path": primary_file.file_path if primary_file else None,
            })
        return results


@mcp.tool()
def assign_tag_to_unit(
    unit_id: int,
    tag_name: str,
    class_code: str = "domain",
    is_primary_landing: bool = False
) -> Dict[str, Any]:
    """为指定资产单元打标。若标签不存在会自动在对应类族下创建"""
    with Session(engine) as session:
        unit = session.get(AssetUnit, unit_id)
        if not unit:
            return {"error": f"AssetUnit with id {unit_id} not found"}

        tag_class = session.exec(select(TagClass).where(TagClass.code == class_code)).first()
        if not tag_class:
            tag_class = TagClass(code=class_code, display_name=class_code)
            session.add(tag_class)
            session.commit()
            session.refresh(tag_class)

        _, norm_name = normalize_tag_name(tag_name)
        tag = session.exec(
            select(Tag).where(Tag.name == tag_name, Tag.tag_class_id == tag_class.id)
        ).first()

        if not tag:
            scoped_norm = f"{norm_name}::{tag_class.id}"
            conflict = session.exec(select(Tag).where(Tag.normalized_name == norm_name)).first()
            tag = Tag(
                name=tag_name,
                normalized_name=scoped_norm if conflict else norm_name,
                tag_class_id=tag_class.id,
            )
            session.add(tag)
            session.commit()
            session.refresh(tag)

        existing_link = session.exec(
            select(AssetUnitTagLink).where(
                AssetUnitTagLink.unit_id == unit_id, AssetUnitTagLink.tag_id == tag.id
            )
        ).first()

        if not existing_link:
            new_link = AssetUnitTagLink(
                unit_id=unit_id,
                tag_id=tag.id,
                is_primary_landing=is_primary_landing,
                confidence=1.0,
            )
            session.add(new_link)
            session.commit()
            TagHierarchyCacheManager.invalidate()
            return {"success": True, "action": "created", "tag_id": tag.id, "tag_name": tag.name}
        else:
            if existing_link.is_primary_landing != is_primary_landing:
                existing_link.is_primary_landing = is_primary_landing
                session.add(existing_link)
                session.commit()
            return {"success": True, "action": "already_exists", "tag_id": tag.id, "tag_name": tag.name}


@mcp.tool()
def batch_assign_tags(assignments: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    批量为多个资产单元打标。
    assignments 每项格式：{"unit_id": 1, "tag_name": "科幻悬疑", "class_code": "domain", "is_primary_landing": false}
    """
    applied = 0
    errors = []
    for item in assignments:
        try:
            res = assign_tag_to_unit(
                unit_id=int(item["unit_id"]),
                tag_name=str(item["tag_name"]).strip(),
                class_code=str(item.get("class_code") or "domain").strip(),
                is_primary_landing=bool(item.get("is_primary_landing", False)),
            )
            if res.get("success"):
                applied += 1
            else:
                errors.append(res)
        except Exception as e:
            errors.append({"item": item, "error": str(e)})
    return {"status": "ok", "applied": applied, "errors": errors}


@mcp.tool()
def remove_tag_from_unit(unit_id: int, tag_name: str) -> Dict[str, Any]:
    """从指定资产单元移除标签关联"""
    with Session(engine) as session:
        _, norm_name = normalize_tag_name(tag_name)
        tag = session.exec(
            select(Tag).where((Tag.normalized_name == norm_name) | (Tag.name == tag_name))
        ).first()
        if not tag:
            return {"error": f"Tag {tag_name} not found"}

        link = session.exec(
            select(AssetUnitTagLink).where(
                AssetUnitTagLink.unit_id == unit_id, AssetUnitTagLink.tag_id == tag.id
            )
        ).first()

        if link:
            session.delete(link)
            session.commit()
            TagHierarchyCacheManager.invalidate()
            return {"success": True, "removed": True}
        return {"success": True, "removed": False, "message": "Link not found"}


@mcp.tool()
def rate_asset_with_telemetry(unit_id: int, rating: int, notes: Optional[str] = None) -> Dict[str, Any]:
    """为资产打分 (1~5 星)，并记入时序显式反馈流水以增强长期共鸣偏好"""
    with Session(engine) as session:
        unit = session.get(AssetUnit, unit_id)
        if not unit:
            return {"error": f"AssetUnit with id {unit_id} not found"}

        unit.rating = max(0, min(5, rating))
        log_entry = TelemetryLog(
            unit_id=unit.id,
            action="rate",
            score=float(rating),
            context_metadata={"notes": notes, "source": "agent_mcp"} if notes else {"source": "agent_mcp"},
            created_at=datetime.now(timezone.utc),
        )
        session.add(log_entry)
        session.add(unit)
        session.commit()
        return {"success": True, "unit_id": unit.id, "new_rating": unit.rating}


@mcp.tool()
def cooldown_asset_unit(unit_id: int, days: int = 14, reason: str = "agent_triage") -> Dict[str, Any]:
    """将资产加入疲劳冷却池，在推荐流中熔断屏蔽指定天数"""
    with Session(engine) as session:
        unit = session.get(AssetUnit, unit_id)
        if not unit:
            return {"error": f"AssetUnit with id {unit_id} not found"}

        cooldown_until = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
        attrs = dict(unit.dynamic_attributes or {})
        attrs["cooldown_until"] = cooldown_until
        unit.dynamic_attributes = attrs

        log_entry = TelemetryLog(
            unit_id=unit.id,
            action="cooldown",
            context_metadata={"days": days, "reason": reason, "cooldown_until": cooldown_until, "source": "agent_mcp"},
            created_at=datetime.now(timezone.utc),
        )
        session.add(log_entry)
        session.add(unit)
        session.commit()
        return {"success": True, "unit_id": unit.id, "cooldown_until": cooldown_until}


@mcp.tool()
def list_collections(parent_id: Optional[int] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """列出合集与系列目录，支持按父级查询子目录树"""
    with Session(engine) as session:
        stmt = select(Collection)
        if parent_id is not None:
            stmt = stmt.where(Collection.parent_id == parent_id)
        cols = session.exec(stmt.limit(limit)).all()
        return [
            {
                "id": c.id,
                "name": c.name,
                "folder_path": c.folder_path,
                "parent_id": c.parent_id,
                "unit_count": session.exec(
                    select(func.count(AssetUnit.id)).where(AssetUnit.collection_id == c.id)
                ).one(),
            }
            for c in cols
        ]


@mcp.tool()
def check_database_health() -> Dict[str, Any]:
    """运行深度数据库一致性检查 (PRAGMA integrity_check, foreign_key_check, 悬空关系排查)"""
    with Session(engine) as session:
        ic = session.execute(text("PRAGMA integrity_check")).fetchall()
        fk = session.execute(text("PRAGMA foreign_key_check")).fetchall()

        orphans = session.execute(
            text("SELECT id FROM assetunit WHERE id NOT IN (SELECT DISTINCT asset_unit_id FROM assetfile)")
        ).fetchall()

        return {
            "integrity_check": [row[0] for row in ic],
            "foreign_key_violations_count": len(fk),
            "orphan_units_count": len(orphans),
            "status": "healthy" if len(fk) == 0 else "unhealthy",
        }


def main():
    """MCP Server 启动主入口，默认使用标准 stdio 通道与外部 Agent 通信"""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
