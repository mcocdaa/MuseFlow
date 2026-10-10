from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.core.config import LLM_BASE_URL, LLM_API_KEY, LLM_MODEL
from app.core.db import get_session
from app.models.entities import AssetUnit, Collection
from app.services.ai_organizer import request_ai_triage, apply_ai_triage_plan

router = APIRouter(prefix="/api/ai", tags=["ai"])

class AIAnalyzeRequest(BaseModel):
    folder_path: str
    instruction: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None

class AIApplyRequest(BaseModel):
    folder_path: str
    plan: Dict[str, Any]

class AISettingsUpdate(BaseModel):
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None

@router.get("/settings")
def get_ai_settings():
    """获取当前 AI 大模型配置"""
    return {
        "base_url": LLM_BASE_URL,
        "model": LLM_MODEL,
        "has_api_key": bool(LLM_API_KEY),
        "api_key_masked": f"{LLM_API_KEY[:6]}...{LLM_API_KEY[-4:]}" if LLM_API_KEY else ""
    }

@router.post("/analyze_folder")
def analyze_folder(payload: AIAnalyzeRequest):
    """
    使用大模型 (如 grok-4.7) 深入分析混乱文件夹拓扑：
    - 识别应提取的子系列 (如 A/a.png, A/B/b.png -> 将 B 提升为独立系列)
    - 解决跨层级/同名/语义配对的复合工程包 (如 A/ep1.srt 与 A/raw/ep1.mp4 绑为单一复合单元)
    - 支持音乐伴侣 (lrc/slc/cue) 与视频伴侣 (srt/vtt/wav)
    """
    try:
        plan = request_ai_triage(
            folder_path_str=payload.folder_path,
            custom_instruction=payload.instruction or "",
            base_url=payload.base_url or LLM_BASE_URL,
            api_key=payload.api_key or LLM_API_KEY,
            model=payload.model or LLM_MODEL
        )
        return plan
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 分析失败: {str(e)}")

@router.post("/apply_triage")
def apply_triage(payload: AIApplyRequest, session: Session = Depends(get_session)):
    """一键应用 AI 整理建议方案至数据库"""
    try:
        res = apply_ai_triage_plan(session, payload.folder_path, payload.plan)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"应用方案失败: {str(e)}")

@router.get("/unorganized")
def get_unorganized_assets(session: Session = Depends(get_session)):
    """获取所有散落、未归入任何系列或从未被评分浏览的资产"""
    units = session.exec(
        select(AssetUnit).where(AssetUnit.collection_id == None).limit(50)
    ).all()
    
    return [
        {
            "id": u.id,
            "title": u.title,
            "unit_type": u.unit_type,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "view_count": u.view_count,
        }
        for u in units
    ]

@router.get("/memory_recap_context")
def get_memory_recap_context(session: Session = Depends(get_session)):
    """向外部大模型/Agent 提供未整理或尘封记忆的统计摘要"""
    stale_units = session.exec(
        select(AssetUnit).where(AssetUnit.view_count == 0).order_by(AssetUnit.created_at.asc()).limit(10)
    ).all()
    
    collections = session.exec(select(Collection).limit(20)).all()
    
    return {
        "stale_memory_count": len(stale_units),
        "sample_stale_units": [{"id": u.id, "title": u.title, "type": u.unit_type} for u in stale_units],
        "existing_collections": [c.name for c in collections],
        "agent_instructions": "This API allows an autonomous AI agent to analyze scattered media, suggest new supersets, and write thematic descriptions."
    }
