from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.core.config import MAX_DWELL_SECONDS
from app.core.db import get_session
from app.models.entities import TelemetryLog, AssetUnit
from app.models.schemas import TelemetryCreate

router = APIRouter(prefix="/api/telemetry", tags=["telemetry"])

@router.post("/log")
def log_interaction(payload: TelemetryCreate, session: Session = Depends(get_session)):
    """记录用户消费行为（点击、有效停留时长、点赞、跳过），并更新热度累加器"""
    unit = session.get(AssetUnit, payload.unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="AssetUnit not found")

    # 防挂机截断：单次停留时长不超过 MAX_DWELL_SECONDS (例如 180s)
    capped_dwell = min(max(0.0, payload.dwell_seconds), MAX_DWELL_SECONDS)

    log_entry = TelemetryLog(
        unit_id=payload.unit_id,
        action=payload.action,
        dwell_seconds=capped_dwell,
        created_at=datetime.now(timezone.utc)
    )
    session.add(log_entry)

    # 累加统计
    if payload.action in ("click", "view"):
        unit.view_count += 1
    if capped_dwell > 0:
        unit.total_dwell_seconds += capped_dwell
    unit.last_viewed_at = datetime.now(timezone.utc)

    session.add(unit)
    session.commit()
    return {"status": "success", "unit_id": payload.unit_id, "dwell_seconds": capped_dwell}
