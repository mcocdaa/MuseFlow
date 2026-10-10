from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session
from app.core.db import get_session
from app.services.physical_organizer import (
    get_active_maintenance_locks,
    inspect_directory_assets,
    plan_metadata_normalization_and_dates,
    plan_workflow_subfolder_isolation,
    plan_interactive_topology,
    execute_triage_plan,
    PhysicalTriagePlan,
)
from app.services.projection_dsl import PipelineConfig

router = APIRouter(prefix="/api/organize", tags=["organize"])

class InspectRequest(BaseModel):
    folder_path: str

class PlanRequest(BaseModel):
    folder_path: str
    rule: str # "metadata_normalization_and_dates", "workflow_subfolder_isolation", "custom_topology"
    options: Optional[Dict[str, Any]] = None

class ExecuteRequest(BaseModel):
    plan: Dict[str, Any]
    dry_run: bool = False

@router.get("/maintenance")
def get_maintenance_status():
    """获取所有当前正在处于物理重组维护中的目录状态与警告原因"""
    return {
        "active_locks": get_active_maintenance_locks(),
        "is_under_maintenance": len(get_active_maintenance_locks()) > 0,
    }

@router.post("/inspect")
def inspect_scope(payload: InspectRequest, session: Session = Depends(get_session)):
    """探查指定物理目录下的媒体资产概况与目录拓扑"""
    res = inspect_directory_assets(session, payload.folder_path)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res

@router.post("/plan")
def generate_triage_plan(payload: PlanRequest, session: Session = Depends(get_session)):
    """根据规则生成物理整理执行计划 (Dry Run 预演)"""
    opts = payload.options or {}
    try:
        if payload.rule == "metadata_normalization_and_dates":
            rename_template = opts.get("rename_template", "{title}")
            update_mtime = opts.get("update_mtime_to_release", True)
            plan = plan_metadata_normalization_and_dates(
                session=session,
                target_folder_str=payload.folder_path,
                rename_template=rename_template,
                update_mtime_to_release=update_mtime,
            )
        elif payload.rule == "workflow_subfolder_isolation":
            subfolder = opts.get("untranslated_subfolder_name", "待整理")
            plan = plan_workflow_subfolder_isolation(
                session=session,
                target_folder_str=payload.folder_path,
                untranslated_subfolder_name=subfolder,
            )
        elif payload.rule == "custom_topology":
            mapping = opts.get("topology_mapping", {})
            summary = opts.get("summary", "用户自定义目录拓扑整理")
            plan = plan_interactive_topology(
                session=session,
                target_folder_str=payload.folder_path,
                topology_mapping=mapping,
                summary=summary,
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unknown organization rule: {payload.rule}")

        return plan.to_dict()
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate plan: {e}")

class PipelineEvaluateRequest(BaseModel):
    pipeline: PipelineConfig
    collection_id: Optional[int] = None
    folder_path: Optional[str] = None

@router.get("/pipeline/presets")
def get_pipeline_presets():
    """获取预设的常用收纳整理流水线模板"""
    return [
        {
            "id": "category_standard",
            "name": "⭐ 题材分类与创作者分流流水线",
            "description": "按「题材/分类」➔「创作者/社团」分层归类，作品名规范统一",
            "levels": [
                {"level_index": 0, "facet": "tag.domain", "fallback": "通用分类"},
                {"level_index": 1, "facet": "tag.creator", "fallback": "独立创作者"},
                {"level_index": 2, "naming": "{unit.title}%unique{}"}
            ]
        },
        {
            "id": "creator_first",
            "name": "👤 创作者/社团优先流水线",
            "description": "按「创作者/社团」➔「题材」分层，作品名保持纯净，同名时自动消歧",
            "levels": [
                {"level_index": 0, "facet": "tag.creator", "fallback": "其他创作者"},
                {"level_index": 1, "facet": "tag.domain", "fallback": "综合作品"},
                {"level_index": 2, "naming": "{unit.title}%unique{meta.code, unit.id}"}
            ]
        },
        {
            "id": "media_kind_clean",
            "name": "📁 媒体形态扁平整理流水线",
            "description": "按「媒体形态」➔「分类」快速两级归类，极度清爽",
            "levels": [
                {"level_index": 0, "facet": "tag.media_kind", "fallback": "媒体"},
                {"level_index": 1, "facet": "tag.domain", "fallback": "精选"},
                {"level_index": 2, "naming": "{unit.title}%unique{}"}
            ]
        }
    ]

@router.post("/pipeline/evaluate")
def evaluate_pipeline(payload: PipelineEvaluateRequest, session: Session = Depends(get_session)):
    """
    根据用户编排的自定义管线规则进行干跑求值与三色风险体检 (Dry-Run AST Evaluation)
    """
    from sqlmodel import select
    from app.models.entities import AssetUnit, Collection
    from app.services.projection_dsl import generate_pipeline_projection_plan

    units_query = select(AssetUnit)
    if payload.collection_id:
        units_query = units_query.where(AssetUnit.collection_id == payload.collection_id)
    elif payload.folder_path:
        cols = session.exec(select(Collection).where(Collection.folder_path.startswith(payload.folder_path))).all()
        col_ids = [c.id for c in cols if c.id]
        if col_ids:
            units_query = units_query.where(AssetUnit.collection_id.in_(col_ids))

    units = list(session.exec(units_query.limit(300)).all())
    if not units:
        raise HTTPException(status_code=404, detail="未在指定作用域内找到可整理的媒体资产单元")

    try:
        plan = generate_pipeline_projection_plan(session, units, payload.pipeline)
        return plan
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"流水线求值失败: {e}")

@router.post("/execute")
def execute_plan(payload: ExecuteRequest, session: Session = Depends(get_session)):
    """
    执行物理整理方案并原子更新数据库路径。
    支持 dry_run=true 进行零风险干跑验证。
    """
    try:
        plan_obj = PhysicalTriagePlan.from_dict(payload.plan)
        res = execute_triage_plan(session, plan_obj, dry_run=payload.dry_run)
        return res
    except RuntimeError as re:
        raise HTTPException(status_code=503, detail=str(re))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to execute reorganization: {e}")

