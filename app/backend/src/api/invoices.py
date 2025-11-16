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
from sqlalchemy import and_, func, or_
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

    (
        prefix,
        company_segment,
        year_segment,
        month_segment,
    ) = build_invoice_storage_components(vendor_company, reference_date)

    zip_filename = f"{company_segment}_{year_segment}_{month_segment}_invoices.zip"
    zip_key = f"{prefix}{zip_filename}"

    legacy_prefix = f"invoices/{company_segment}/{normalized_month}/"
    legacy_zip_filename = f"{company_segment}_{normalized_month}_invoices.zip"
    legacy_zip_key = f"{legacy_prefix}{legacy_zip_filename}"

    client = get_s3_client()

    LOGGER.info(
        "invoice_zip_request_received",
        vendor_id=vendor_id,
        company=company_segment,
        month=normalized_month,
        user=current_user.email,
    )

    def _build_presigned_url(target_key: str) -> str:
        download_name = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(target_key).name)
        params = {
            "Bucket": bucket_name,
            "Key": sanitize_object_key(target_key),
            "ResponseContentDisposition": f'attachment; filename="{download_name}"',
            "ResponseContentType": "application/zip",
        }
        return client.generate_presigned_url(
            "get_object",
            Params=params,
            ExpiresIn=3600,
        )

    async def _object_exists(target_key: str) -> bool:
        try:
            await run_in_threadpool(
                client.head_object, Bucket=bucket_name, Key=target_key
            )
            return True
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            if error_code not in {"404", "NoSuchKey", "NotFound"}:
                LOGGER.error(
                    "invoice_zip_head_failed",
                    vendor_id=vendor_id,
                    company=company_segment,
                    month=normalized_month,
                    key=target_key,
                    error=str(exc),
                )
                raise HTTPException(
                    status_code=502, detail="Unable to access invoice archive"
                )
        except BotoCoreError as exc:
            LOGGER.error(
                "invoice_zip_head_error",
                vendor_id=vendor_id,
                company=company_segment,
                month=normalized_month,
                key=target_key,
                error=str(exc),
            )
            raise HTTPException(status_code=502, detail="Unable to access invoice archive")
        return False

    if await _object_exists(zip_key):
        try:
            url = await run_in_threadpool(_build_presigned_url, zip_key)
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
            "invoice_zip_reused",
            vendor_id=vendor_id,
            company=company_segment,
            month=normalized_month,
            key=zip_key,
        )
        LOGGER.info(
            "invoice_zip_success",
            vendor_id=vendor_id,
            company=company_segment,
            month=normalized_month,
            key=zip_key,
        )
        return {"download_url": url}

    if await _object_exists(legacy_zip_key):
        try:
            url = await run_in_threadpool(_build_presigned_url, legacy_zip_key)
        except (ClientError, BotoCoreError) as exc:
            LOGGER.error(
                "invoice_zip_presign_failed",
                vendor_id=vendor_id,
                company=company_segment,
                month=normalized_month,
                key=legacy_zip_key,
                error=str(exc),
            )
            raise HTTPException(status_code=502, detail="Unable to generate download link")

        LOGGER.info(
            "invoice_zip_reused",
            vendor_id=vendor_id,
            company=company_segment,
            month=normalized_month,
            key=legacy_zip_key,
        )
        LOGGER.info(
            "invoice_zip_success",
            vendor_id=vendor_id,
            company=company_segment,
            month=normalized_month,
            key=legacy_zip_key,
        )
        return {"download_url": url}

    def _list_invoice_objects(target_prefix: str) -> list[dict[str, object]]:
        paginator = client.get_paginator("list_objects_v2")
        objects: list[dict[str, object]] = []
        for page in paginator.paginate(Bucket=bucket_name, Prefix=target_prefix):
            contents = page.get("Contents", []) or []
            for entry in contents:
                key = entry.get("Key")
                if not key:
                    continue
                if key == zip_key or key == legacy_zip_key or str(key).endswith("/"):
                    continue
                objects.append(entry)
        return objects

    selected_prefix = prefix
    try:
        invoice_objects = await run_in_threadpool(_list_invoice_objects, prefix)
    except (ClientError, BotoCoreError) as exc:
        LOGGER.error(
            "invoice_zip_list_failed",
            vendor_id=vendor_id,
            company=company_segment,
            month=normalized_month,
            prefix=prefix,
            error=str(exc),
        )
        raise HTTPException(status_code=502, detail="Unable to enumerate invoices")

    if not invoice_objects:
        try:
            invoice_objects = await run_in_threadpool(
                _list_invoice_objects, legacy_prefix
            )
            selected_prefix = legacy_prefix
        except (ClientError, BotoCoreError) as exc:
            LOGGER.error(
                "invoice_zip_list_failed",
                vendor_id=vendor_id,
                company=company_segment,
                month=normalized_month,
                prefix=legacy_prefix,
                error=str(exc),
            )
            raise HTTPException(status_code=502, detail="Unable to enumerate invoices")

    if not invoice_objects:
        LOGGER.warning(
            "invoice_zip_no_pdfs",
            vendor_id=vendor_id,
            company=company_segment,
            month=normalized_month,
            prefix=selected_prefix,
        )
        raise HTTPException(status_code=404, detail="No invoices available for this month")

    invoices = (
        session.query(Invoice)
        .filter(Invoice.vendor_id == vendor_id)
        .order_by(Invoice.invoice_date.desc(), Invoice.created_at.desc())
        .all()
    )

    vendor_record = session.get(Vendor, vendor_id)
    vendor_display_name = (
        (vendor_record.company_name or "").strip() if vendor_record else ""
    ) or vendor_company

    target_year = reference_date.year
    target_month = reference_date.month

    invoice_lookup: dict[str, Invoice] = {}
    invoice_lookup_by_name: dict[str, Invoice] = {}

    for invoice in invoices:
        period_year, period_month = _determine_invoice_period(invoice)
        if period_year != target_year or period_month != target_month:
            continue

        for attr in ("s3_key", "pdf_s3_key"):
            key_value = getattr(invoice, attr, None)
            if not key_value:
                continue

            normalized_key = str(key_value).strip()
            if not normalized_key:
                continue

            sanitized_key = sanitize_object_key(normalized_key)
            invoice_lookup[normalized_key] = invoice
            invoice_lookup[sanitized_key] = invoice
            invoice_lookup_by_name[Path(normalized_key).name] = invoice
            invoice_lookup_by_name[Path(sanitized_key).name] = invoice

    def _build_zip() -> bytes:
        buffer = BytesIO()
        summary_rows: list[tuple[str, str, str, str]] = []
        with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
            for entry in invoice_objects:
                key = str(entry["Key"])
                file_buffer = BytesIO()
                client.download_fileobj(
                    Bucket=bucket_name,
                    Key=key,
                    Fileobj=file_buffer,
                )
                file_buffer.seek(0)
                archive.writestr(Path(key).name, file_buffer.read())

                invoice = invoice_lookup.get(key) or invoice_lookup.get(
                    sanitize_object_key(key)
                )
                if invoice is None:
                    invoice = invoice_lookup_by_name.get(Path(key).name)

                if invoice:
                    amount_value = Decimal(invoice.total_cost or 0).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )
                    amount_display = format(amount_value, ".2f")
                    uploaded_at = _format_uploaded_at(
                        invoice.invoice_date or getattr(invoice, "created_at", None)
                    )
                else:
                    amount_display = ""
                    uploaded_at = None

                if not uploaded_at:
                    uploaded_at = _format_uploaded_at(entry.get("LastModified"))

                display_name = _format_invoice_name_for_export(Path(key).name)

                summary_rows.append(
                    (
                        vendor_display_name,
                        display_name,
                        amount_display,
                        uploaded_at or "",
                    )
                )

            csv_buffer = StringIO()
            writer = csv.writer(csv_buffer)
            writer.writerow(["Vendor", "Invoice Name", "Amount", "Uploaded At"])
            writer.writerows(summary_rows)
            archive.writestr("invoice_summary.csv", csv_buffer.getvalue())

        buffer.seek(0)
        return buffer.read()

    try:
        zip_payload = await run_in_threadpool(_build_zip)
    except (ClientError, BotoCoreError) as exc:
        LOGGER.error(
            "invoice_zip_build_failed",
            vendor_id=vendor_id,
            month=normalized_month,
            prefix=prefix,
            error=str(exc),
        )
        raise HTTPException(status_code=502, detail="Unable to build invoice archive")

    def _upload_zip(payload: bytes) -> None:
        client.upload_fileobj(
            Fileobj=BytesIO(payload),
            Bucket=bucket_name,
            Key=zip_key,
            ExtraArgs={"ContentType": "application/zip"},
        )

    try:
        await run_in_threadpool(_upload_zip, zip_payload)
        LOGGER.info(
            "invoice_zip_created",
            vendor_id=vendor_id,
            company=company_segment,
            month=normalized_month,
            key=zip_key,
            file_count=len(invoice_objects),
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

    try:
        download_url = await run_in_threadpool(_build_presigned_url, zip_key)
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
    return {"download_url": download_url}


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

    vendor_company = _resolve_vendor_company_name(session, vendor_id)
    (
        prefix,
        company_segment,
        year_segment,
        month_segment,
    ) = build_invoice_storage_components(vendor_company, reference_date)

    LOGGER.info(
        "district_invoice_listing_requested",
        vendor_id=vendor_id,
        company=company_segment,
        year=year_segment,
        month=month_segment,
        user=current_user.email,
    )

    vendor_company_display = vendor.company_name or company_segment

    try:
        reference_start = datetime(year, month, 1, tzinfo=timezone.utc)
        reference_end = (
            datetime(year + 1, 1, 1, tzinfo=timezone.utc)
            if month == 12
            else datetime(year, month + 1, 1, tzinfo=timezone.utc)
        )
    except ValueError as exc:  # pragma: no cover - defensive guard
        raise HTTPException(status_code=400, detail="Invalid invoice period") from exc

    period_filter = or_(
        and_(Invoice.service_year == year, Invoice.service_month_num == month),
        and_(
            or_(
                Invoice.service_year.is_(None),
                Invoice.service_month_num.is_(None),
            ),
            Invoice.invoice_date >= reference_start,
            Invoice.invoice_date < reference_end,
        ),
    )

    aggregates = (
        session.query(
            Invoice.student_name.label("student_name"),
            func.sum(Invoice.total_cost).label("total_amount"),
            func.max(Invoice.invoice_date).label("latest_invoice_date"),
            func.max(Invoice.id).label("latest_invoice_id"),
        )
        .filter(Invoice.vendor_id == vendor_id)
        .filter(period_filter)
        .group_by(Invoice.student_name)
        .all()
    )

    latest_invoice_ids = [entry.latest_invoice_id for entry in aggregates if entry.latest_invoice_id]
    invoice_lookup: dict[int, Invoice] = {}
    if latest_invoice_ids:
        invoice_lookup = {
            invoice.id: invoice
            for invoice in session.query(Invoice)
            .filter(Invoice.id.in_(latest_invoice_ids))
            .all()
        }

    results: list[dict[str, object]] = []
    for entry in aggregates:
        invoice = invoice_lookup.get(entry.latest_invoice_id)
        student_name = (entry.student_name or "").strip()
        amount_value = Decimal(entry.total_amount or 0).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        uploaded_at = _format_uploaded_at(
            getattr(invoice, "invoice_date", None)
            or getattr(invoice, "created_at", None)
            or entry.latest_invoice_date
        )
        status_value = (
            getattr(invoice, "status", "") if invoice is not None else ""
        ).strip()
        s3_key = None
        if invoice is not None:
            s3_key = getattr(invoice, "s3_key", None) or getattr(
                invoice, "pdf_s3_key", None
            )

        invoice_id = getattr(invoice, "id", None) or entry.latest_invoice_id

        results.append(
            {
                "invoice_ids": [invoice_id] if invoice_id else [],
                "invoice_id": invoice_id,
                "vendor_id": getattr(invoice, "vendor_id", vendor_id),
                "company": vendor_company_display,
                "invoice_name": student_name or f"Invoice {invoice_id}",
                "student_name": student_name or None,
                "s3_key": s3_key,
                "amount": float(amount_value),
                "status": status_value,
                "uploaded_at": uploaded_at,
            }
        )
        results.append(entry)

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
        company=company_segment,
        year=year_segment,
        month=month_segment,
        prefix_used=prefix,
        count=len(results),
    )

    return results
