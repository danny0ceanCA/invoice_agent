"""Invoice related endpoints."""

from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.backend.src.core.security import require_vendor_user
from ..db import get_session_dependency
from app.backend.src.models import Job, User
try:
    from invoice_agent.tasks.invoice_tasks import process_invoice
except ModuleNotFoundError:  # pragma: no cover
    from tasks.invoice_tasks import process_invoice

LOGGER = structlog.get_logger(__name__)

router = APIRouter(prefix="/invoices", tags=["invoices"])



def _select_queue(file_size: int) -> str:
    if file_size < 10_000_000:
        return "small"
    if file_size < 40_000_000:
        return "medium"
    return "large"


@router.post("/generate")
async def generate_invoices(
    file: UploadFile = File(...),
    vendor_id: int = Form(...),
    invoice_date: str = Form(...),
    service_month: str = Form(...),
    invoice_code: str | None = Form(None),
    session: Session = Depends(get_session_dependency),
    current_user: User = Depends(require_vendor_user),
) -> dict[str, str]:
    """Trigger the invoice processing pipeline for a vendor upload."""

    if current_user.vendor_id != vendor_id:
        raise HTTPException(status_code=403, detail="Access to vendor denied")

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    queue = _select_queue(len(contents))
    LOGGER.info(
        "invoice_upload_received",
        filename=file.filename,
        vendor_id=vendor_id,
        queue=queue,
        size=len(contents),
    )
    with NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp_file:
        tmp_file.write(contents)
        temp_path = Path(tmp_file.name)

    LOGGER.info(
        "enqueue_invoice_task",
        vendor_id=vendor_id,
        queue=queue,
        temp_path=str(temp_path),
    )
    task = process_invoice.apply_async(
        args=[str(temp_path), vendor_id, invoice_date, service_month, invoice_code],
        kwargs={"queue_name": queue},
        queue=queue,
    )

    LOGGER.info(
        "invoice_task_enqueued",
        task_id=task.id,
        vendor_id=vendor_id,
        queue=queue,
    )

    job = Job(
        id=task.id,
        user_id=current_user.id,
        vendor_id=vendor_id,
        filename=file.filename,
        queue=queue,
        status="queued",
    )
    session.add(job)
    session.commit()

    return {"job_id": task.id, "status": job.status}
