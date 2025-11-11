"""Invoice related endpoints."""

from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile

import structlog
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    Query,
)
from sqlalchemy.orm import Session

from app.backend.src.core.security import (
    require_vendor_user,
    get_current_user,
)
from app.backend.src.models import Job, User
from app.backend.src.services.s3 import generate_presigned_url
from ..db import get_session_dependency

try:
    from invoice_agent.tasks.invoice_tasks import process_invoice
except ModuleNotFoundError:  # pragma: no cover
    from tasks.invoice_tasks import process_invoice

LOGGER = structlog.get_logger(__name__)

router = APIRouter(prefix="/invoices", tags=["invoices"])


# --------------------------------------------------------------------------
# Utility: Select Celery queue based on file size
# --------------------------------------------------------------------------
def _select_queue(file_size: int) -> str:
    if file_size < 10_000_000:
        return "small"
    if file_size < 40_000_000:
        return "medium"
    return "large"


# --------------------------------------------------------------------------
# POST /invoices/generate
# --------------------------------------------------------------------------
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

    # Enqueue the Celery task
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

    # Record the job in the database
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


# --------------------------------------------------------------------------
# GET /invoices/presign
# --------------------------------------------------------------------------
@router.get("/presign")
def presign_invoice_file(
    s3_key: str = Query(..., description="Full S3 key of the stored invoice PDF"),
    current_user: User = Depends(get_current_user),
):
    """
    Return a presigned S3 URL so authenticated users can download invoice PDFs.

    - Works for both vendor and district roles.
    - Accepts the full S3 key as a query parameter.
    - Responds with a JSON object: {"url": "<presigned_s3_url>"}.
    """

    LOGGER.info("presign_request_received", user=current_user.email, s3_key=s3_key)

    if not s3_key:
        raise HTTPException(status_code=400, detail="Missing S3 key")

    try:
        url = generate_presigned_url(
            key=s3_key,
            download_name=Path(s3_key).name,
            response_content_type="application/pdf",
        )
        LOGGER.info("presign_success", s3_key=s3_key, url_preview=url[:80])
        return {"url": url}

    except Exception as exc:
        LOGGER.error("presign_failed", s3_key=s3_key, error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to generate presigned URL")
