"""Celery tasks for invoice processing."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import structlog

from app.backend.src.agents.invoice_agent import InvoiceAgent
from app.backend.src.services.metrics import job_duration_seconds
from .worker import celery

LOGGER = structlog.get_logger(__name__)


@celery.task(name="tasks.process_invoice")
def process_invoice(
    upload_path: str,
    vendor_id: int,
    invoice_date: str,
    service_month: str,
    invoice_code: str | None = None,
    queue_name: str = "small",
) -> dict[str, Any]:
    """Trigger invoice processing for a newly uploaded file."""

    start = perf_counter()
    try:
        parsed_invoice_date = datetime.fromisoformat(invoice_date)
    except ValueError:
        parsed_invoice_date = datetime.strptime(invoice_date, "%Y-%m-%d")

    job_id = process_invoice.request.id if hasattr(process_invoice, "request") else None
    agent = InvoiceAgent(
        vendor_id=vendor_id,
        invoice_date=parsed_invoice_date,
        service_month=service_month,
        invoice_code=invoice_code,
        job_id=job_id,
    )
    try:
        result = agent.run(Path(upload_path))
        LOGGER.info("celery_job_success", upload=upload_path, queue=queue_name)
        return result
    except Exception as exc:  # pragma: no cover - logged and re-raised
        LOGGER.error("celery_job_failure", error=str(exc), upload=upload_path)
        raise
    finally:
        job_duration_seconds.labels(queue=queue_name).observe(perf_counter() - start)
        Path(upload_path).unlink(missing_ok=True)


__all__ = ["process_invoice"]
