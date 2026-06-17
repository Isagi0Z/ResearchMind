import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from backend.api.app import app
from backend.api.services.monitoring_service import MonitoringService
from backend.api.schemas.monitoring import MonitoringSnapshot
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.mark.asyncio
async def test_monitoring_service_returns_snapshot():
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock()

    mock_result = MagicMock()
    mock_result.scalar.return_value = 0
    db.execute.return_value = mock_result

    service = MonitoringService(db)
    snapshot = await service.get_snapshot("24h")

    assert isinstance(snapshot, MonitoringSnapshot)
    assert len(snapshot.health) == 6
    assert snapshot.health[0].moduleId == "m1"
    assert snapshot.metrics["queriesExecuted"] == 0
    assert snapshot.metrics["registeredUsers"] == 0
    assert snapshot.metrics["activeUsers"] == 0
    assert snapshot.metrics["reviewsGenerated"] == 0
    assert snapshot.metrics["reviewsToday"] == 0
    assert snapshot.metrics["documentsProcessed"] == 0
    assert snapshot.metrics["refreshTokensActive"] == 0
    assert snapshot.queue == []
    assert snapshot.recentErrors == []


@pytest.mark.asyncio
async def test_monitoring_service_hourly_buckets():
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock(return_value=MagicMock(scalar=MagicMock(return_value=0)))

    service = MonitoringService(db)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=2)
    charts = await service._hourly_buckets(cutoff)

    assert len(charts) >= 2
    for c in charts:
        assert c.throughput == 0.0
        assert c.latencyMs == 0.0
        assert c.successRate == 1.0


@pytest.mark.asyncio
async def test_monitoring_service_success_rate_empty():
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock(return_value=MagicMock(scalar=MagicMock(return_value=0)))

    service = MonitoringService(db)
    rate = await service._success_rate()

    assert rate == 1.0


@pytest.mark.asyncio
async def test_monitoring_service_time_range_default():
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock(return_value=MagicMock(scalar=MagicMock(return_value=5)))

    service = MonitoringService(db)
    snapshot = await service.get_snapshot("7d")

    assert isinstance(snapshot, MonitoringSnapshot)


def test_monitoring_endpoint_requires_auth(client):
    response = client.get("/api/v1/monitoring")
    assert response.status_code == 401


def test_monitoring_metrics_endpoint_requires_auth(client):
    response = client.get("/api/v1/monitoring/metrics")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_monitoring_service_cutoff():
    db = AsyncMock(spec=AsyncSession)
    service = MonitoringService(db)

    c1h = service._cutoff("1h")
    c24h = service._cutoff("24h")
    c7d = service._cutoff("7d")
    c30d = service._cutoff("30d")

    now = datetime.now(timezone.utc)
    assert abs((now - c1h).total_seconds() - 3600) < 10
    assert abs((now - c24h).total_seconds() - 86400) < 10
    assert abs((now - c7d).total_seconds() - 604800) < 10
    assert abs((now - c30d).total_seconds() - 2592000) < 10


@pytest.mark.asyncio
async def test_monitoring_service_default_time_range():
    db = AsyncMock(spec=AsyncSession)
    service = MonitoringService(db)
    assert service._cutoff("invalid") <= service._cutoff("24h")
