"""Endpoints to track Celery job status."""

from __future__ import annotations

from datetime import datetime, timezone

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.backend.src.core.security import require_vendor_user
from app.backend.src.db import get_session_dependency
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
        "message": job.message,
    }


@router.get("/{job_id}")
def job_status(
    job_id: str,
    session: Session = Depends(get_session_dependency),
    current_user: User = Depends(require_vendor_user),
) -> dict[str, str | None]:
    """Return the status of a background job if it belongs to the current user."""

    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if current_user.role != "admin" and job.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Job not found")

    result = AsyncResult(job_id, app=celery)
    job.updated_at = datetime.now(timezone.utc)

    if result.successful():
        payload = result.result or {}
        status = payload.get("status") or job.status or "completed"
        job.status = status
        zip_key = payload.get("zip_s3_key")
        job.result_key = zip_key or None
        if payload.get("message"):
            job.message = payload["message"]
    elif result.failed():
        job.status = "error"
        job.error_message = str(result.result)
        job.message = job.message or job.error_message
    else:
        state = result.state.lower()
        normalized = (
            "queued"
            if state in {"pending"}
            else "running"
            if state in {"started", "received"}
            else state
        )
        if job.status not in {"completed", "skipped", "error"}:
            job.status = normalized

    session.add(job)
    session.commit()
    return _serialize_job(job)


@router.get("")
def list_jobs(
    session: Session = Depends(get_session_dependency),
    current_user: User = Depends(require_vendor_user),
) -> list[dict[str, str | None]]:
    """Return the most recent jobs for the authenticated user."""

    query = session.query(Job).order_by(Job.created_at.desc())
    if current_user.role != "admin":
        query = query.filter(Job.user_id == current_user.id)

    jobs = query.limit(20).all()
    return [_serialize_job(job) for job in jobs]
