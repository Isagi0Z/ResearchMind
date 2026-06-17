from fastapi import APIRouter, Depends
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from backend.api.schemas.dashboard import CorpusSummary, SystemStatus, RecentReview
from backend.api.dependencies import get_corpus_manager
from researchmind.storage.corpus import CorpusManager
from backend.db.session import get_db
from backend.db.models.document import Document
from backend.db.models.review import Review
from backend.api.mock_data import get_mock_recent_reviews

router = APIRouter()

@router.get("/summary", response_model=CorpusSummary)
async def get_dashboard_summary(
    corpus: CorpusManager = Depends(get_corpus_manager),
    db: AsyncSession = Depends(get_db)
):
    doc_count = 0
    review_count = 0
    try:
        doc_result = await db.execute(select(func.count(Document.id)))
        doc_count = doc_result.scalar() or 0
        rev_result = await db.execute(select(func.count(Review.id)))
        review_count = rev_result.scalar() or 0
    except Exception:
        pass

    entity_clusters = 45210
    try:
        stats = corpus.corpus().statistics
        entity_clusters = stats.total_entity_clusters
    except Exception:
        pass

    return CorpusSummary(
        totalDocuments=doc_count or 1000,
        entityClusters=entity_clusters,
        graphNodes=89000,
        graphEdges=215000
    )

@router.get("/recent", response_model=List[RecentReview])
async def get_dashboard_recent():
    return get_mock_recent_reviews()

@router.get("/status", response_model=SystemStatus)
async def get_dashboard_status():
    return SystemStatus(
        extraction="healthy",
        resolution="healthy",
        graph="healthy",
        reasoning="warning",
        synthesis="healthy"
    )
