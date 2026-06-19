import uuid as uuid_lib
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from backend.db.session import get_db
from backend.api.dependencies import get_corpus_manager, get_current_user_optional
from backend.api.services.document_service import DocumentService
from backend.api.schemas.documents import PaginatedDocumentsResponse
from backend.api.schemas.jobs import JobSubmitResponse
from backend.db.models.job import Job
from backend.db.models.user import User
from backend.tasks import jobs as task_jobs
from researchmind.storage.corpus import CorpusManager

router = APIRouter()


async def _get_document_service(
    db: AsyncSession = Depends(get_db),
    corpus: CorpusManager = Depends(get_corpus_manager),
) -> DocumentService:
    return DocumentService(db, corpus)


@router.get("", response_model=PaginatedDocumentsResponse)
async def get_documents(
    pageIndex: int = Query(0, ge=0, alias="pageIndex"),
    pageSize: int = Query(10, ge=1, le=1000, alias="pageSize"),
    searchQuery: Optional[str] = Query(None, alias="searchQuery"),
    sortBy: Optional[str] = Query(None, alias="sortBy"),
    sortDirection: str = Query("desc", alias="sortDirection"),
    service: DocumentService = Depends(_get_document_service),
):
    return await service.list_documents(
        page_index=pageIndex,
        page_size=pageSize,
        search_query=searchQuery,
        sort_by=sortBy,
        sort_direction=sortDirection,
    )


@router.post("/process", response_model=JobSubmitResponse)
async def process_documents(
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    user_id = current_user.id if current_user else uuid_lib.uuid4()
    job = Job(
        user_id=user_id,
        job_type="document_processing",
        status="queued",
        progress=0,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    task_jobs.process_documents.delay(
        job_id=str(job.id),
        corpus_id="corpus-1",
    )

    return JobSubmitResponse(job_id=str(job.id), status="queued")


@router.get("/{id}")
async def get_document(
    id: str,
    service: DocumentService = Depends(_get_document_service),
):
    detail = await service.get_document(id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Document not found")
    full = await service.get_full_document(id)
    if full is not None:
        stages = full.meta.pipeline_stages or []
        detail.pipeline_stages = stages
        detail.abstract = full.abstract.content if full.abstract else None
    return detail
