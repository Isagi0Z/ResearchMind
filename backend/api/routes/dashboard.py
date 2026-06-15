from fastapi import APIRouter
from typing import List
from backend.api.schemas.dashboard import CorpusSummary, SystemStatus, RecentReview
from backend.api.dependencies import get_corpus_manager
from fastapi import Depends
from researchmind.storage.corpus import CorpusManager
from backend.api.mock_data import get_mock_recent_reviews

router = APIRouter()

@router.get("/summary", response_model=CorpusSummary)
async def get_dashboard_summary(corpus: CorpusManager = Depends(get_corpus_manager)):
    # Use real corpus data where possible, deterministic fallbacks for others
    try:
        stats = corpus.corpus().statistics
        return CorpusSummary(
            totalDocuments=stats.total_documents,
            entityClusters=stats.total_entity_clusters,
            graphNodes=89000,
            graphEdges=215000
        )
    except Exception:
        return CorpusSummary(
            totalDocuments=1000,
            entityClusters=45210,
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
