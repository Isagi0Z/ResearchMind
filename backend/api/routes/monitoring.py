from fastapi import APIRouter, Query, Depends
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from backend.db.session import get_db
from backend.api.schemas.monitoring import MonitoringSnapshot
from backend.api.services.monitoring_service import MonitoringService
from backend.api.dependencies import get_current_active_user, require_role
from backend.db.models.user import User

router = APIRouter()

@router.get("", response_model=MonitoringSnapshot)
async def get_monitoring(
    timeRange: Optional[str] = Query("24h", alias="timeRange"),
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    service = MonitoringService(db)
    return await service.get_snapshot(timeRange)

@router.get("/metrics", response_model=MonitoringSnapshot)
async def get_monitoring_metrics(
    timeRange: Optional[str] = Query("24h", alias="timeRange"),
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    service = MonitoringService(db)
    return await service.get_snapshot(timeRange)
