import json
import uuid
import asyncio
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text as sql_text
from typing import Optional

from backend.db.session import get_db, async_session_factory
from backend.db.models.job import Job
from backend.db.models.user import User
from backend.api.dependencies import get_current_user, get_current_active_user
from backend.api.schemas.jobs import JobResponse, JobListResponse, JobSubmitResponse
from backend.tasks.celery_app import celery_app
from backend.tasks import jobs as task_jobs

router = APIRouter()


async def _job_to_response(job) -> JobResponse:
    result_ref = None
    if isinstance(job, Job):
        if job.result_reference:
            try:
                result_ref = json.loads(job.result_reference)
            except (json.JSONDecodeError, TypeError):
                result_ref = job.result_reference
        return JobResponse(
            id=str(job.id),
            user_id=str(job.user_id),
            job_type=job.job_type,
            status=job.status,
            progress=job.progress,
            error_message=job.error_message,
            result_reference=result_ref,
            created_at=job.created_at,
            updated_at=job.updated_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
        )
    return JobResponse(
        id=str(job[0]),
        user_id=str(job[1]),
        job_type=job[2],
        status=job[3],
        progress=job[4],
        error_message=job[5],
        result_reference=job[6],
        created_at=job[7],
        updated_at=job[8],
        started_at=job[9],
        completed_at=job[10],
    )


@router.get("/jobs", response_model=JobListResponse)
async def list_jobs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    pageIndex: int = Query(0, ge=0, alias="pageIndex"),
    pageSize: int = Query(20, ge=1, le=200, alias="pageSize"),
    status: Optional[str] = Query(None),
    job_type: Optional[str] = Query(None),
):
    query = select(Job)
    if current_user.role != "admin":
        query = query.where(Job.user_id == current_user.id)
    if status:
        query = query.where(Job.status == status)
    if job_type:
        query = query.where(Job.job_type == job_type)
    query = query.order_by(Job.created_at.desc()).offset(pageIndex).limit(pageSize)
    result = await db.execute(query)
    jobs = result.scalars().all()

    count_query = select(func.count(Job.id))
    if current_user.role != "admin":
        count_query = count_query.where(Job.user_id == current_user.id)
    if status:
        count_query = count_query.where(Job.status == status)
    if job_type:
        count_query = count_query.where(Job.job_type == job_type)
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    return JobListResponse(
        data=[await _job_to_response(j) for j in jobs],
        total=total,
    )


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Job not found")
    result = await db.execute(select(Job).where(Job.id == job_uuid))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if current_user.role != "admin" and job.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return await _job_to_response(job)


@router.get("/jobs/{job_id}/events")
async def job_events(
    job_id: str,
    current_user: User = Depends(get_current_active_user),
):
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Job not found")

    async with async_session_factory() as verify_session:
        result = await verify_session.execute(select(Job).where(Job.id == job_uuid))
        job = result.scalar_one_or_none()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if current_user.role != "admin" and job.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")

    async def event_generator():
        poll_interval = 1.0
        last_status = None
        last_progress = -1
        while True:
            try:
                async with async_session_factory() as poll_session:
                    result = await poll_session.execute(
                        select(
                            Job.status,
                            Job.progress,
                            Job.error_message,
                            Job.completed_at,
                        ).where(Job.id == job_uuid)
                    )
                    row = result.fetchone()
                if not row:
                    yield f"event: error\ndata: {json.dumps({'message': 'Job not found'})}\n\n"
                    break
                status, progress, error_message, completed_at = row
                event_data = json.dumps({
                    "status": status,
                    "progress": progress,
                    "error_message": error_message,
                })
                if status != last_status or progress != last_progress:
                    yield f"event: progress\ndata: {event_data}\n\n"
                    last_status = status
                    last_progress = progress
                if status in ("completed", "failed"):
                    break
            except Exception:
                yield f"event: error\ndata: {json.dumps({'message': 'Polling error'})}\n\n"
                break
            await asyncio.sleep(poll_interval)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
