from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from app.core.db import get_session
from app.models.entities import AssetUnit, Collection

router = APIRouter(prefix="/api/ai", tags=["ai"])

class TriageSuggestion(BaseModel):
    unit_id: int
    title: str
    suggested_collection_name: str
    reason: str

class BatchTagRequest(BaseModel):
    unit_ids: List[int]
    tags: List[str]
    superset_name: Optional[str] = None

@router.get("/unorganized")
def get_unorganized_assets(session: Session = Depends(get_session)):
    """获取所有散落、未归入任何系列或从未被评分浏览的资产，方便 AI Agent 接管处理"""
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
    """向外部大模型/Agent 提供未整理或尘封记忆的统计摘要，用于生成'今日回忆'或'待整理建议'"""
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
