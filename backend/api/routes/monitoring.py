from fastapi import APIRouter
from backend.api.schemas.monitoring import MonitoringSnapshot
from backend.api.mock_graph import generate_mock_monitoring
from datetime import datetime

router = APIRouter()

@router.get("", response_model=MonitoringSnapshot)
async def get_monitoring():
    # Use a deterministic time range string like "24h"
    return generate_mock_monitoring("24h")

@router.get("/metrics", response_model=MonitoringSnapshot)
async def get_monitoring_metrics():
    return generate_mock_monitoring("24h")
