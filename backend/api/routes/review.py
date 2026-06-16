from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from researchmind.synthesis.orchestrator import ReviewOrchestrator
from researchmind.synthesis.traceability import TraceabilityVerifier
from researchmind.synthesis.models import ReviewRequest, ReviewResult

from backend.api.dependencies import (
    get_review_orchestrator,
    get_traceability_verifier,
    get_corpus_manager,
    get_current_user_optional
)
from backend.db.session import get_db
from backend.db.models.review import Review
from backend.db.models.user import User

router = APIRouter()

@router.post("/generate")
async def generate_review(
    request: ReviewRequest,
    orchestrator: ReviewOrchestrator = Depends(get_review_orchestrator),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    try:
        result = orchestrator.generate(request)
        result_dump = result.model_dump()
        
        if current_user:
            db_review = Review(
                user_id=current_user.id,
                title=request.topic,
                review_result=result_dump,
                metadata_={"target_audience": request.target_audience}
            )
            db.add(db_review)
            await db.commit()

        return {"review_result": result_dump}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/validate")
async def validate_review(
    request: ReviewResult,
    verifier: TraceabilityVerifier = Depends(get_traceability_verifier),
    corpus = Depends(get_corpus_manager)
):
    try:
        is_valid, errors = verifier.verify_review(request, corpus)
        return {"traceability_report": {"is_valid": is_valid, "errors": errors}}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
