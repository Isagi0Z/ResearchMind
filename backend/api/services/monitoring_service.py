from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func as sa_func
from backend.db.models.query import Query
from backend.db.models.review import Review
from backend.db.models.user import User
from backend.db.models.document import Document
from backend.db.models.refresh_token import RefreshToken
from backend.api.schemas.monitoring import (
    MonitoringSnapshot,
    ModuleHealth,
    PerformanceMetric,
    CorpusStatistic,
)
import time

TIME_RANGES = {
    "1h": timedelta(hours=1),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}

MODULES = [
    {"id": "m1", "name": "M1 Extraction Engine"},
    {"id": "m2", "name": "M2 Entity Resolution"},
    {"id": "m3", "name": "M3 Corpus Graph"},
    {"id": "m4", "name": "M4 Reasoning Engine"},
    {"id": "m5", "name": "M5 Query System"},
    {"id": "m6", "name": "M6 Synthesis Engine"},
]


class MonitoringService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _cutoff(self, time_range: str) -> datetime:
        delta = TIME_RANGES.get(time_range, TIME_RANGES["24h"])
        return datetime.now(timezone.utc) - delta

    async def _count(self, model, column=None, since: datetime = None) -> int:
        q = select(sa_func.count())
        if since is not None and hasattr(model, "created_at"):
            q = q.where(model.created_at >= since)
        result = await self.db.execute(q.select_from(model))
        return result.scalar() or 0

    async def _success_rate(self, since: datetime = None) -> float:
        q_total = select(sa_func.count()).select_from(Query)
        q_success = select(sa_func.count()).select_from(Query).where(Query.result.isnot(None))
        if since is not None:
            q_total = q_total.where(Query.created_at >= since)
            q_success = q_success.where(Query.created_at >= since)
        total = (await self.db.execute(q_total)).scalar() or 0
        if total == 0:
            return 1.0
        success = (await self.db.execute(q_success)).scalar() or 0
        return round(success / total, 3)

    async def _hourly_buckets(self, since: datetime) -> list:
        now = datetime.now(timezone.utc)
        hours = []
        cursor = now.replace(minute=0, second=0, microsecond=0)
        while cursor > since:
            hours.append(cursor)
            cursor -= timedelta(hours=1)

        charts = []
        for i, hour_start in enumerate(reversed(hours)):
            hour_end = hour_start + timedelta(hours=1)
            q_queries = (
                select(sa_func.count())
                .select_from(Query)
                .where(Query.created_at >= hour_start, Query.created_at < hour_end)
            )
            q_ok = (
                select(sa_func.count())
                .select_from(Query)
                .where(
                    Query.created_at >= hour_start,
                    Query.created_at < hour_end,
                    Query.result.isnot(None),
                )
            )
            total = (await self.db.execute(q_queries)).scalar() or 0
            ok = (await self.db.execute(q_ok)).scalar() or 0
            charts.append(
                PerformanceMetric(
                    label=hour_start.strftime("%H:%M"),
                    throughput=float(total),
                    latencyMs=0.0,
                    successRate=round(ok / total, 3) if total > 0 else 1.0,
                )
            )
        return charts

    async def get_snapshot(self, time_range: str) -> MonitoringSnapshot:
        cutoff = self._cutoff(time_range)

        total_queries = await self._count(Query, since=None)
        queries_today = await self._count(Query, since=cutoff)
        total_reviews = await self._count(Review, since=None)
        reviews_today = await self._count(Review, since=cutoff)
        total_users = await self._count(User, since=None)
        active_users_count = (
            await self.db.execute(
                select(sa_func.count()).select_from(User).where(User.is_active == True)
            )
        ).scalar() or 0
        total_docs = await self._count(Document, since=None)
        refresh_count = (
            await self.db.execute(
                select(sa_func.count())
                .select_from(RefreshToken)
                .where(RefreshToken.is_revoked == False)
            )
        ).scalar() or 0
        success_rate = await self._success_rate(since=cutoff)
        charts = await self._hourly_buckets(cutoff)

        return MonitoringSnapshot(
            id=f"snap-{int(time.time())}",
            health=[
                ModuleHealth(
                    moduleId=m["id"],
                    name=m["name"],
                    status="Healthy",
                    uptime="—",
                    activeThreads=0,
                )
                for m in MODULES
            ],
            metrics={
                "queriesExecuted": total_queries,
                "queriesToday": queries_today,
                "querySuccessRate": success_rate,
                "reviewsGenerated": total_reviews,
                "reviewsToday": reviews_today,
                "registeredUsers": total_users,
                "activeUsers": active_users_count,
                "refreshTokensActive": refresh_count,
                "documentsProcessed": total_docs,
            },
            charts=charts,
            queue=[],
            recentErrors=[],
            corpus=CorpusStatistic(
                documentCount=total_docs,
                authorCount=0,
                entityCount=0,
                reviewCount=total_reviews,
            ),
        )
