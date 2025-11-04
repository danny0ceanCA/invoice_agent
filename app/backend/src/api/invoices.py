"""Invoice related endpoints."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.backend.src.agents.invoice_agent import InvoiceAgent
from app.backend.src.core.security import get_current_user
from app.backend.src.db import get_session_dependency
from app.backend.src.models import Job, User
try:
    from invoice_agent.tasks.invoice_tasks import process_invoice
except ModuleNotFoundError:  # pragma: no cover
    from tasks.invoice_tasks import process_invoice

router = APIRouter(prefix="/invoices", tags=["invoices"])


LOGGER = structlog.get_logger(__name__)



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
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Trigger the invoice processing pipeline for a vendor upload."""

    if current_user.vendor_id != vendor_id:
        raise HTTPException(status_code=403, detail="Access to vendor denied")

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    queue = _select_queue(len(contents))
    with NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp_file:
        tmp_file.write(contents)
        temp_path = Path(tmp_file.name)

    try:
        task = process_invoice.apply_async(
            args=[str(temp_path), vendor_id, invoice_date, service_month, invoice_code],
            kwargs={"queue_name": queue},
            queue=queue,
        )
    except Exception as exc:  # pragma: no cover - exercised in tests via monkeypatch
        LOGGER.warning("celery_unavailable", error=str(exc), queue=queue)
        inline_job_id = f"inline-{uuid4().hex}"
        try:
            parsed_invoice_date = datetime.fromisoformat(invoice_date)
        except ValueError:
            parsed_invoice_date = datetime.strptime(invoice_date, "%Y-%m-%d")

        agent = InvoiceAgent(
            vendor_id=vendor_id,
            invoice_date=parsed_invoice_date,
            service_month=service_month,
            invoice_code=invoice_code,
            job_id=inline_job_id,
        )
        try:
            result = agent.run(temp_path)
        finally:
            temp_path.unlink(missing_ok=True)

        job = Job(
            id=inline_job_id,
            user_id=current_user.id,
            vendor_id=vendor_id,
            filename=file.filename,
            queue="inline",
            status=result.get("status", "completed"),
            message=result.get("message"),
            result_key=(result.get("zip_s3_key") or None),
        )
        session.add(job)
        session.commit()

        return {
            "job_id": job.id,
            "status": job.status,
            "message": job.message,
            "queue": job.queue,
        }

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

    return {"job_id": task.id, "status": job.status, "queue": job.queue, "message": job.message}
