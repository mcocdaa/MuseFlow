from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select
from app.core.db import get_session
from app.models.entities import AssetFile, AssetUnit
from app.models.schemas import SystemActionRequest
from app.services.native_os import open_in_file_explorer, open_with_default_app

router = APIRouter(prefix="/api/system", tags=["system"])

def resolve_target_path(payload: SystemActionRequest, session: Session) -> str:
    if payload.path:
        return payload.path

    if payload.file_id:
        f = session.get(AssetFile, payload.file_id)
        if f:
            return f.file_path

    if payload.unit_id:
        unit = session.get(AssetUnit, payload.unit_id)
        if unit:
            f = session.exec(select(AssetFile).where(AssetFile.asset_unit_id == unit.id, AssetFile.role == "primary")).first()
            if f:
                return f.file_path
            f_any = session.exec(select(AssetFile).where(AssetFile.asset_unit_id == unit.id)).first()
            if f_any:
                return f_any.file_path

    raise HTTPException(status_code=400, detail="Cannot resolve physical path from provided parameters")

@router.post("/reveal")
def reveal_in_explorer(payload: SystemActionRequest, session: Session = Depends(get_session)):
    """在操作系统文件资源管理器中定位并选中文件"""
    path_str = resolve_target_path(payload, session)
    success = open_in_file_explorer(path_str)
    if not success:
        raise HTTPException(status_code=500, detail=f"Failed to reveal path in OS explorer: {path_str}")
    return {"status": "success", "path": path_str}

@router.post("/open")
def open_externally(payload: SystemActionRequest, session: Session = Depends(get_session)):
    """调用操作系统默认程序打开文件"""
    path_str = resolve_target_path(payload, session)
    success = open_with_default_app(path_str)
    if not success:
        raise HTTPException(status_code=500, detail=f"Failed to open with default app: {path_str}")
    return {"status": "success", "path": path_str}

class RemapPathRequest(BaseModel):
    old_prefix: str
    new_prefix: str

@router.post("/remap_path")
def remap_storage_path(payload: RemapPathRequest, session: Session = Depends(get_session)):
    r"""
    动态重映射存储路径前缀（如从 \\NAS-SERVER\media 迁移到 /mnt/nas 或新 NAS 挂载点），
    无损批量更新 AssetFile 与 Collection 路径，完好保留所有虚拟超集、收藏夹与播放历史。
    """
    old_p = payload.old_prefix.replace("\\", "/").rstrip("/")
    new_p = payload.new_prefix.replace("\\", "/").rstrip("/")

    files = session.exec(select(AssetFile)).all()
    file_count = 0
    for f in files:
        f_norm = f.file_path.replace("\\", "/")
        if f_norm.startswith(old_p):
            f.file_path = new_p + f_norm[len(old_p):]
            session.add(f)
            file_count += 1

    cols = session.exec(select(Collection)).all()
    col_count = 0
    for c in cols:
        if c.folder_path:
            c_norm = c.folder_path.replace("\\", "/")
            if c_norm.startswith(old_p):
                c.folder_path = new_p + c_norm[len(old_p):]
                session.add(c)
                col_count += 1

    session.commit()
    return {
        "status": "success",
        "remapped_files": file_count,
        "remapped_collections": col_count,
        "old_prefix": payload.old_prefix,
        "new_prefix": payload.new_prefix,
    }

@router.get("/mcp_config")
def get_mcp_config():
    """获取外部 Coding Agent (Claude Desktop / Cursor / Antigravity) 的标准 MCP 配置与已就绪工具清单"""
    import shutil
    import sys
    backend_dir = str(Path(__file__).resolve().parent.parent.parent)
    uv_path = shutil.which("uv") or "uv"

    return {
        "status": "ready",
        "server_name": "museflow",
        "transport": "stdio",
        "project_path": backend_dir,
        "config_json": {
            "mcpServers": {
                "museflow": {
                    "command": uv_path,
                    "args": ["run", "python", "-m", "app.mcp.server"],
                    "cwd": backend_dir,
                }
            }
        },
        "tools": [
            {"name": "get_taxonomy_tree", "desc": "读取多维分类与标签树（含关联数与同义词别名），用于深入分析指定标签列"},
            {"name": "organize_tag_column", "desc": "对标签列执行批量深度规整（同义词合并、上下位树归纳、跨维度迁移、去噪）"},
            {"name": "analyze_collection_topology", "desc": "导出合集系列与物理目录结构，用于识别嵌套子系列与跨目录复合包"},
            {"name": "restructure_collection_series", "desc": "将 Agent 生成的系列拆分与复合包配对方案无损应用至数据库"},
            {"name": "batch_assign_tags", "desc": "批量为多个资产单元打标与设置落点锚点"},
            {"name": "get_library_stats", "desc": "获取全库资产、文件、标签、合集统计与不变量健康状态"},
            {"name": "search_assets", "desc": "全文多维检索资产单元及主文件路径"},
            {"name": "get_asset_details", "desc": "获取资产单元挂载的所有物理文件、关联多维标签及属性"},
            {"name": "get_untagged_assets", "desc": "查找缺少标签或尚未打标的资产单元，用于批量治理"},
            {"name": "assign_tag_to_unit", "desc": "为指定资产单元挂载面向对象多维标签"},
            {"name": "remove_tag_from_unit", "desc": "从指定资产单元移除标签关联"},
            {"name": "rate_asset_with_telemetry", "desc": "为资产打分并记入时序显式反馈增强长期共鸣偏好"},
            {"name": "cooldown_asset_unit", "desc": "将资产加入疲劳冷却池，在推荐流中熔断屏蔽"},
            {"name": "list_collections", "desc": "列出合集与系列目录树及子目录"},
            {"name": "check_database_health", "desc": "运行深度数据库完整性、外键与孤儿数据审计"},
        ],
    }

@router.get("/mount_status")
def get_storage_mount_status():
    """检测 NAS 与物理媒体目录挂载状态"""
    from app.services.sync_engine import check_mount_status
    return check_mount_status()

@router.post("/sync_changes")
def sync_physical_library_changes(session: Session = Depends(get_session)):
    """增量热同步物理 NAS 的新增、改名、移动与删除变更"""
    from app.services.sync_engine import sync_library_changes
    return sync_library_changes(session, prune_missing=True)

@router.post("/reindex_all")
def wipe_and_reindex_library(session: Session = Depends(get_session)):
    """清空旧媒体数据并重新全量扫描与反向打标构建"""
    from app.services.sync_engine import wipe_and_rebuild_all
    return wipe_and_rebuild_all(session)
