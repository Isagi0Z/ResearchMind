import json
import uuid
from datetime import datetime, timezone
from sqlalchemy import text
from backend.tasks.celery_app import celery_app
from backend.tasks.session import get_sync_db
from backend.db.models.job import Job


def _update_job(job_id: str, **kwargs):
    db = get_sync_db()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            for k, v in kwargs.items():
                setattr(job, k, v)
            db.commit()
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def process_documents(self, job_id: str, corpus_id: str):
    _update_job(job_id, status="running", started_at=datetime.now(timezone.utc))
    try:
        total_docs = 10
        for i in range(total_docs):
            progress = int(((i + 1) / total_docs) * 100)
            _update_job(job_id, progress=progress)
        _update_job(
            job_id,
            status="completed",
            progress=100,
            completed_at=datetime.now(timezone.utc),
            result_reference=json.dumps({"documents_processed": total_docs}),
        )
    except Exception as exc:
        _update_job(
            job_id,
            status="failed",
            completed_at=datetime.now(timezone.utc),
            error_message=str(exc),
        )
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=3)
def generate_review(self, job_id: str, review_request_json: str):
    _update_job(job_id, status="running", started_at=datetime.now(timezone.utc))
    try:
        from researchmind.synthesis.orchestrator import ReviewOrchestrator
        from researchmind.synthesis.models import ReviewRequest
        from backend.api.dependencies import _corpus_manager, _graph

        request_data = json.loads(review_request_json)
        review_request = ReviewRequest(**request_data)
        orchestrator = ReviewOrchestrator(
            corpus_manager=_corpus_manager,
            graph=_graph,
        )
        _update_job(job_id, progress=10)
        result = orchestrator.generate(review_request)
        _update_job(job_id, progress=90)
        result_dump = result.model_dump()
        _update_job(
            job_id,
            status="completed",
            progress=100,
            completed_at=datetime.now(timezone.utc),
            result_reference=json.dumps(result_dump),
        )
    except Exception as exc:
        _update_job(
            job_id,
            status="failed",
            completed_at=datetime.now(timezone.utc),
            error_message=str(exc),
        )
        raise self.retry(exc=exc)
