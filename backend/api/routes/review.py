from fastapi import APIRouter, Depends, HTTPException
from researchmind.synthesis.orchestrator import ReviewOrchestrator
from researchmind.synthesis.traceability import TraceabilityVerifier
from researchmind.synthesis.models import ReviewRequest, ReviewResult

from backend.api.dependencies import (
    get_review_orchestrator,
    get_traceability_verifier,
    get_corpus_manager,
)

router = APIRouter()

@router.post("/generate")
async def generate_review(
    request: ReviewRequest,
    orchestrator: ReviewOrchestrator = Depends(get_review_orchestrator)
):
    try:
        result = orchestrator.generate(request)
        return {"review_result": result.model_dump()}
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
