import json
import uuid as uuid_lib
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional, List

from researchmind.synthesis.orchestrator import ReviewOrchestrator
from researchmind.synthesis.traceability import TraceabilityVerifier
from researchmind.synthesis.models import ReviewRequest, ReviewResult

from backend.api.dependencies import (
    get_review_orchestrator,
    get_traceability_verifier,
    get_corpus_manager,
    get_current_user_optional,
    get_current_active_user
)
from backend.db.session import get_db
from backend.db.models.review import Review as ReviewModel
from backend.db.models.job import Job
from backend.db.models.user import User
from backend.api.schemas.review import ReviewHistoryResponse
from backend.api.schemas.jobs import JobSubmitResponse
from backend.tasks import jobs as task_jobs
from backend.api.config import settings
from fastapi import Query as QueryParam

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
            db_review = ReviewModel(
                user_id=current_user.id,
                title=request.title,
                review_result=result_dump,
                metadata_=request.metadata
            )
            db.add(db_review)
            await db.commit()

        return {"review_result": result_dump}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/generate-async", response_model=JobSubmitResponse)
async def generate_review_async(
    request: ReviewRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    user_id = current_user.id if current_user else uuid_lib.uuid4()
    job = Job(
        user_id=user_id,
        job_type="review_generation",
        status="queued",
        progress=0,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    task_jobs.generate_review.delay(
        job_id=str(job.id),
        review_request_json=request.model_dump_json(),
    )

    return JobSubmitResponse(job_id=str(job.id), status="queued")

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

@router.get("/history", response_model=List[ReviewHistoryResponse])
async def get_review_history(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    skip: int = QueryParam(default=0, ge=0),
    limit: int = QueryParam(default=50, ge=1, le=200)
):
    result = await db.execute(
        select(ReviewModel).where(ReviewModel.user_id == current_user.id).order_by(ReviewModel.created_at.desc()).offset(skip).limit(limit)
    )
    reviews = result.scalars().all()
    return [
        ReviewHistoryResponse(
            id=str(r.id),
            title=r.title or "",
            created_at=str(r.created_at)
        )
        for r in reviews
    ]
