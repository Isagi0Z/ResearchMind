from fastapi import APIRouter, Query, Depends
from typing import Optional
from backend.api.schemas.monitoring import MonitoringSnapshot
from backend.api.mock_graph import generate_mock_monitoring
from backend.api.dependencies import get_current_active_user, require_role
from backend.db.models.user import User
from datetime import datetime

router = APIRouter()

@router.get("", response_model=MonitoringSnapshot)
async def get_monitoring(
    timeRange: Optional[str] = Query("24h", alias="timeRange"),
    current_user: User = Depends(require_role("admin"))
):
    return generate_mock_monitoring(timeRange)

@router.get("/metrics", response_model=MonitoringSnapshot)
async def get_monitoring_metrics(
    timeRange: Optional[str] = Query("24h", alias="timeRange"),
    current_user: User = Depends(require_role("admin"))
):
    return generate_mock_monitoring(timeRange)
