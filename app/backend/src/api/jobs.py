"""Endpoints for inspecting background jobs."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.backend.src.core.db import get_db
from app.backend.src.models.job import Job
from app.backend.src.schemas.job import JobRead

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[JobRead])
async def list_jobs(session: Session = Depends(get_db)) -> list[JobRead]:
    """Return all job records sorted by creation time."""

    jobs = session.execute(select(Job).order_by(Job.created_at.desc())).scalars().all()
    return [
        JobRead(
            id=job.id,
            vendor_id=job.vendor_id,
            invoice_id=job.invoice_id,
            filename=job.filename,
            status=job.status,
            message=job.message,
            created_at=job.created_at,
            download_url=f"/api/invoices/{job.invoice_id}/pdf" if job.invoice_id else None,
        )
        for job in jobs
    ]
