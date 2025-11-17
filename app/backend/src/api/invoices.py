"""Invoice related endpoints."""

from __future__ import annotations

import csv
import re
from calendar import month_abbr, month_name
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO, StringIO
from pathlib import Path
from tempfile import NamedTemporaryFile
from zipfile import ZipFile, ZIP_DEFLATED

import structlog
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    Query,
)
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.backend.src.core.security import (
    require_vendor_user,
    get_current_user,
    require_district_user,
)
from app.backend.src.models import Invoice, Job, User, Vendor
from app.backend.src.services.s3 import (
    build_invoice_storage_components,
    generate_presigned_url,
    get_s3_client,
    sanitize_object_key,
)
from app.backend.src.core.config import get_settings
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


def _resolve_vendor_company_name(session: Session, vendor_id: int) -> str:
    try:
        vendor: Vendor | None = session.get(Vendor, vendor_id)
    except Exception as exc:  # pragma: no cover - defensive fallback
        LOGGER.warning(
            "vendor_lookup_failed",
            vendor_id=vendor_id,
            error=str(exc),
        )
        return f"vendor-{vendor_id}"

    if vendor and vendor.company_name:
        return vendor.company_name
    return f"vendor-{vendor_id}"


def _resolve_year_month(month_token: str) -> tuple[str, str]:
    candidate = (month_token or "").strip()
    for fmt in ("%Y-%m", "%Y/%m", "%m-%Y", "%m/%Y", "%B %Y", "%b %Y"):
        try:
            parsed = datetime.strptime(candidate, fmt)
            return f"{parsed.year:04d}", f"{parsed.month:02d}"
        except ValueError:
            continue

    match = re.search(r"(?P<year>\d{4}).*?(?P<month>\d{1,2})", candidate)
    if match:
        year = match.group("year")
        month = match.group("month").zfill(2)
        return year, month

    fallback = datetime.utcnow()
    return f"{fallback.year:04d}", f"{fallback.month:02d}"


# --------------------------------------------------------------------------
# Utility: Month parsing helpers
# --------------------------------------------------------------------------
_MONTH_LOOKUP = {
    name.lower(): index
    for index, name in enumerate(month_name)
    if name
}
_MONTH_LOOKUP.update(
    {
        name.lower(): index
        for index, name in enumerate(month_abbr)
        if name
    }
)


def _parse_service_month_tokens(value: str | None) -> tuple[int | None, int | None]:
    """Attempt to extract year and month from a service month string."""

    if not value:
        return None, None

    candidate = value.strip()
    if not candidate:
        return None, None

    for fmt in ("%Y-%m", "%Y/%m", "%m-%Y", "%m/%Y", "%B %Y", "%b %Y"):
        try:
            parsed = datetime.strptime(candidate, fmt)
            return parsed.year, parsed.month
        except ValueError:
            continue

    year_match = re.search(r"(20\d{2}|19\d{2})", candidate)
    month_match = None
    if year_match:
        year_value = int(year_match.group(0))
        tokens = re.split(r"[^A-Za-z]+", candidate)
        for token in tokens:
            if not token:
                continue
            lookup = _MONTH_LOOKUP.get(token.lower())
            if lookup:
                return year_value, lookup
        month_match = re.search(r"(?P<month>1[0-2]|0?[1-9])", candidate)
        if month_match:
            return year_value, int(month_match.group("month"))

    return None, None


def _determine_invoice_period(invoice: Invoice) -> tuple[int | None, int | None]:
    """Return the (year, month) tuple for an invoice."""

    invoice_date = getattr(invoice, "invoice_date", None)
    if invoice_date:
        return invoice_date.year, invoice_date.month

    service_year, service_month = _parse_service_month_tokens(
        getattr(invoice, "service_month", None)
    )
    return service_year, service_month


def _format_uploaded_at(value: datetime | None) -> str | None:
    """Format timestamps as ISO 8601 with UTC normalization."""

    if not value:
        return None

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)

    return value.isoformat().replace("+00:00", "Z")


def _format_invoice_name_for_export(key: str) -> str:
    if not key:
        return ""

    base_name = Path(key).stem
    clean_name = re.sub(r"_[0-9a-f]{32}$", "", base_name, flags=re.IGNORECASE)
    clean_name = re.sub(r"^Invoice_", "", clean_name)
    parts = clean_name.split("_")
    if len(parts) > 2 and len(parts[0]) > 1:
        first_name, last_name, *rest = parts
        compressed = f"{first_name[0]}{last_name}" if last_name else first_name[0]
        if rest:
            return "_".join([compressed, *rest])
        return compressed
    return "_".join(parts)


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


# --------------------------------------------------------------------------
# GET /invoices/download/{invoice_id}
# --------------------------------------------------------------------------
@router.get("/download/{invoice_id}")
def download_invoice(
    invoice_id: int,
    current_user: User = Depends(require_district_user),
    session: Session = Depends(get_session_dependency),
) -> dict[str, str]:
    """Return a presigned URL for a specific invoice PDF."""

    if invoice_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid invoice identifier")

    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    pdf_s3_key = getattr(invoice, "pdf_s3_key", None)
    if not pdf_s3_key:
        raise HTTPException(status_code=404, detail="Invoice PDF not available")

    sanitized_key = sanitize_object_key(str(pdf_s3_key))

    settings = get_settings()
    bucket_name = settings.aws_s3_bucket or "invoice-agent-files"
    if bucket_name.lower() == "local":
        bucket_name = "invoice-agent-files"

    client = get_s3_client()

    LOGGER.info(
        "invoice_download_request_received",
        invoice_id=invoice_id,
        user=current_user.email,
        bucket=bucket_name,
        key_preview=sanitized_key[:80],
    )

    try:
        url = client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": bucket_name,
                "Key": sanitized_key,
                "ResponseContentDisposition": f'inline; filename="{Path(sanitized_key).name}"',
                "ResponseContentType": "application/pdf",
            },
            ExpiresIn=3600,
        )
    except (ClientError, BotoCoreError) as exc:
        LOGGER.error(
            "invoice_download_presign_failed",
            invoice_id=invoice_id,
            error=str(exc),
        )
        raise HTTPException(status_code=502, detail="Unable to generate download link") from exc

    LOGGER.info("invoice_download_presign_success", invoice_id=invoice_id)

    return {"url": url}


# --------------------------------------------------------------------------
# GET /invoices/download-zip/{vendor_id}/{month}
# --------------------------------------------------------------------------
@router.get("/download-zip/{vendor_id}/{month}")
async def download_invoices_zip(
    vendor_id: int,
    month: str,
    current_user: User = Depends(require_district_user),
    session: Session = Depends(get_session_dependency),
) -> dict[str, str]:
    """Return a presigned URL for a vendor's monthly invoice archive."""

    if vendor_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid vendor identifier")

    normalized_month = (month or "").strip().strip("/")
    if not normalized_month or ".." in normalized_month:
        raise HTTPException(status_code=400, detail="Invalid month value")

    settings = get_settings()
    bucket_name = settings.aws_s3_bucket or "invoice-agent-files"
    if bucket_name.lower() == "local":
        bucket_name = "invoice-agent-files"

    vendor_company = _resolve_vendor_company_name(session, vendor_id)
    year_token, month_token = _resolve_year_month(normalized_month)

    try:
        reference_date = datetime(int(year_token), int(month_token), 1)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid month value") from None

    target_year = reference_date.year
    target_month = reference_date.month

    (
        prefix,
        company_segment,
        year_segment,
        month_segment,
    ) = build_invoice_storage_components(vendor_company, reference_date)

    client = get_s3_client()

    LOGGER.info(
        "invoice_zip_request_received",
        vendor_id=vendor_id,
        company=company_segment,
        month=normalized_month,
        user=current_user.email,
    )

    invoices = (
        session.query(Invoice)
        .filter(Invoice.vendor_id == vendor_id)
        .filter(Invoice.service_year == target_year)
        .filter(Invoice.service_month_num == target_month)
        .order_by(Invoice.student_name.asc())
        .all()
    )

    pdf_keys: list[tuple[str, Invoice]] = []
    summary_rows: list[list[object]] = []

    for invoice in invoices:
        key = getattr(invoice, "pdf_s3_key", None)
        if not key:
            continue

        sanitized = sanitize_object_key(str(key).strip())
        if not sanitized:
            continue

        pdf_keys.append((sanitized, invoice))
        summary_rows.append(
            [
                (invoice.student_name or "").strip(),
                str(invoice.id),
                float(invoice.total_cost or 0),
                (invoice.status or "").strip(),
                sanitized,
            ]
        )

    if not pdf_keys:
        LOGGER.warning(
            "invoice_zip_no_objects",
            vendor_id=vendor_id,
            company=company_segment,
            month=normalized_month,
        )
        raise HTTPException(status_code=404, detail="No invoices available for this month")

    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as zf:
        for s3_key, invoice in pdf_keys:
            try:
                obj = await run_in_threadpool(
                    client.get_object, Bucket=bucket_name, Key=s3_key
                )
                body = obj["Body"].read()
            except (ClientError, BotoCoreError) as exc:
                LOGGER.error(
                    "invoice_zip_fetch_failed",
                    vendor_id=vendor_id,
                    company=company_segment,
                    month=normalized_month,
                    key=s3_key,
                    error=str(exc),
                )
                raise HTTPException(
                    status_code=502, detail="Unable to read invoice files"
                ) from exc

            student_slug = re.sub(
                r"[^A-Za-z0-9._-]+",
                "_",
                (invoice.student_name or "").strip() or "invoice",
            )
            arcname = f"{student_slug}_{year_segment}_{month_segment}.pdf"
            zf.writestr(arcname, body)

        csv_buffer = StringIO()
        writer = csv.writer(csv_buffer)
        writer.writerow(
            ["student_name", "invoice_id", "total_cost", "status", "pdf_s3_key"]
        )
        writer.writerows(summary_rows)
        zf.writestr("invoice_summary.csv", csv_buffer.getvalue())

    zip_bytes = buffer.getvalue()

    zip_key = f"{prefix}{company_segment}_{year_segment}_{month_segment}_invoices_dynamic.zip"
    zip_key = sanitize_object_key(zip_key)

    try:
        await run_in_threadpool(
            client.put_object,
            Bucket=bucket_name,
            Key=zip_key,
            Body=zip_bytes,
            ContentType="application/zip",
        )
    except (ClientError, BotoCoreError) as exc:
        LOGGER.error(
            "invoice_zip_upload_failed",
            vendor_id=vendor_id,
            company=company_segment,
            month=normalized_month,
            key=zip_key,
            error=str(exc),
        )
        raise HTTPException(status_code=502, detail="Unable to store invoice archive")

    download_name = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(zip_key).name)
    params = {
        "Bucket": bucket_name,
        "Key": zip_key,
        "ResponseContentDisposition": f'attachment; filename="{download_name}"',
        "ResponseContentType": "application/zip",
    }

    try:
        url = client.generate_presigned_url(
            "get_object", Params=params, ExpiresIn=3600
        )
    except (ClientError, BotoCoreError) as exc:
        LOGGER.error(
            "invoice_zip_presign_failed",
            vendor_id=vendor_id,
            company=company_segment,
            month=normalized_month,
            key=zip_key,
            error=str(exc),
        )
        raise HTTPException(status_code=502, detail="Unable to generate download link")

    LOGGER.info(
        "invoice_zip_success",
        vendor_id=vendor_id,
        company=company_segment,
        month=normalized_month,
        key=zip_key,
    )
    return {"url": url}


# --------------------------------------------------------------------------
# GET /invoices/{vendor_id}/{year}/{month}
# --------------------------------------------------------------------------
@router.get("/{vendor_id}/{year}/{month}")
def list_vendor_invoices(
    vendor_id: int,
    year: int,
    month: int,
    session: Session = Depends(get_session_dependency),
    current_user: User = Depends(require_district_user),
) -> list[dict[str, object]]:
    """Return invoice metadata for a vendor in a specific month."""

    if vendor_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid vendor identifier")

    if month <= 0 or month > 12:
        raise HTTPException(status_code=400, detail="Invalid month value")

    if year <= 0:
        raise HTTPException(status_code=400, detail="Invalid year value")

    vendor = session.get(Vendor, vendor_id)
    if vendor is None:
        raise HTTPException(status_code=404, detail="Vendor not found")

    try:
        reference_date = datetime(year, month, 1)
    except ValueError as exc:  # pragma: no cover - defensive guard
        raise HTTPException(status_code=400, detail="Invalid invoice period") from exc

    LOGGER.info(
        "district_invoice_listing_requested",
        vendor_id=vendor_id,
        year=year,
        month=month,
        user=current_user.email,
    )

    invoices = (
        session.query(Invoice)
        .filter(Invoice.vendor_id == vendor_id)
        .filter(Invoice.service_year == year)
        .filter(Invoice.service_month_num == month)
        .all()
    )

    results: list[dict[str, object]] = []
    for invoice in invoices:
        uploaded_at = _format_uploaded_at(
            getattr(invoice, "invoice_date", None) or getattr(invoice, "created_at", None)
        )

        amount_value = Decimal(invoice.total_cost or 0).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        results.append(
            {
                "invoice_id": invoice.id,
                "student_name": (invoice.student_name or "").strip() or None,
                "total_cost": float(amount_value),
                "pdf_s3_key": invoice.pdf_s3_key,
                "uploaded_at": uploaded_at,
                "status": (invoice.status or "").strip(),
            }
        )

    results.sort(
        key=lambda entry: (
            entry.get("uploaded_at") or "",
            entry.get("invoice_id") or 0,
        ),
        reverse=True,
    )

    LOGGER.info(
        "district_invoice_listing_ready",
        vendor_id=vendor_id,
        year=year,
        month=month,
        count=len(results),
    )

    for entry in results:
        entry.pop("uploaded_at", None)

    return results
