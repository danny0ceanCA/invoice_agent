"""Endpoints to track Celery job status."""

from __future__ import annotations

from datetime import datetime, timezone

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.backend.src.core.security import get_current_user
from app.backend.src.db import get_session
from app.backend.src.models import Job, User
from app.backend.src.services.s3 import generate_presigned_url
try:
    from invoice_agent.tasks.worker import celery
except ModuleNotFoundError:  # pragma: no cover
    from tasks.worker import celery

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _serialize_job(job: Job) -> dict[str, str | None]:
    return {
        "id": job.id,
        "filename": job.filename,
        "status": job.status,
        "queue": job.queue,
        "download_url": generate_presigned_url(job.result_key) if job.result_key else None,
        "created_at": job.created_at.isoformat() if job.created_at else None,
    }


@router.get("/{job_id}")
def job_status(
    job_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict[str, str | None]:
    """Return the status of a background job if it belongs to the current user."""

    job = session.get(Job, job_id)
    if job is None or job.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Job not found")

    result = AsyncResult(job_id, app=celery)
    job.updated_at = datetime.now(timezone.utc)

    if result.successful():
        payload = result.result or {}
        job.status = "done"
        job.result_key = payload.get("zip_s3_key")
    elif result.failed():
        job.status = "error"
        job.error_message = str(result.result)
    else:
        job.status = result.state.lower()

    session.add(job)
    session.commit()
    return _serialize_job(job)


@router.get("")
def list_jobs(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[dict[str, str | None]]:
    """Return the most recent jobs for the authenticated user."""

    jobs = (
        session.query(Job)
        .filter(Job.user_id == current_user.id)
        .order_by(Job.created_at.desc())
        .limit(20)
        .all()
    )
    return [_serialize_job(job) for job in jobs]
