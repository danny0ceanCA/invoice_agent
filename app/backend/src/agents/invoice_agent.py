"""Production-grade invoice processing agent."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd
import structlog
from sqlalchemy.orm import Session

from ..db import session_scope
from ..models.invoice import Invoice
from ..models.job import Job
from ..models.line_item import InvoiceLineItem
from ..services.metrics import invoice_jobs_total
from ..services.pdf_generation import InvoicePdf, generate_invoice_pdf
from ..services.s3 import upload_bytes

LOGGER = structlog.get_logger(__name__)

REQUIRED_COLUMNS = ["Client", "Schedule Date", "Hours", "Employee", "Service Code"]


def generate_invoice_number(student_name: str, service_month: datetime) -> str:
    """Return a human-friendly invoice number for a student and month."""

    parts = re.split(r"\s+", student_name.strip())
    last_name = parts[-1].capitalize() if parts else "Unknown"
    month_token = service_month.strftime("%b").upper()
    year_token = service_month.strftime("%Y")
    return f"{last_name}-{month_token}{year_token}"


class InvoiceAgent:
    """Automates transformation of uploaded spreadsheets into invoices."""

    def __init__(
        self,
        vendor_id: int,
        invoice_date: datetime,
        service_month: str | datetime,
        invoice_code: str | None = None,
        *,
        job_id: str | None = None,
        rates: dict[str, float] | None = None,
    ) -> None:
        self.vendor_id = vendor_id
        self.invoice_date = invoice_date
        self.service_month_display, self.service_month_date = self._normalize_service_month(
            service_month, invoice_date
        )
        self.invoice_code = invoice_code or ""
        self.job_id = job_id
        self.rates = rates or {
            "HHA-SCUSD": 55,
            "LVN-SCUSD": 70,
            "RN-SCUSD": 85,
        }
        self.logger = LOGGER.bind(
            vendor_id=vendor_id, service_month=self.service_month_display, job_id=job_id
        )

    def run(self, file_path: Path) -> dict[str, Any]:
        """Execute the end-to-end invoice generation pipeline."""

        try:
            dataframe = pd.read_excel(file_path)
        except Exception as exc:
            invoice_jobs_total.labels(status="failed").inc()
            self.logger.error("invoice_read_failed", error=str(exc))
            raise

        missing = [column for column in REQUIRED_COLUMNS if column not in dataframe.columns]
        if missing:
            invoice_jobs_total.labels(status="failed").inc()
            raise ValueError(f"Missing required columns: {missing}")

        invoices: list[Invoice] = []
        duplicates: list[str] = []
        pdf_artifacts: list[InvoicePdf] = []
        invoice_audit_log: list[dict[str, Any]] = []
        self.logger.info("invoice_agent_start", upload=str(file_path))
        try:
            with session_scope() as session:
                for student, student_frame in dataframe.groupby("Client"):
                    invoice_number = generate_invoice_number(student, self.service_month_date)
                    if self._invoice_exists(session, invoice_number):
                        duplicates.append(invoice_number)
                        self.logger.warning(
                            "duplicate_invoice_skipped",
                            student=student,
                            invoice_number=invoice_number,
                        )
                        continue

                    invoice, pdf_artifact = self._process_student(
                        session, student, student_frame, invoice_number
                    )
                    invoices.append(invoice)
                    pdf_artifacts.append(pdf_artifact)
                    invoice_audit_log.append(
                        {
                            "id": invoice.id,
                            "student": invoice.student_name,
                            "s3_key": invoice.s3_key,
                        }
                    )
        except Exception as exc:
            invoice_jobs_total.labels(status="failed").inc()
            self.logger.error("invoice_agent_error", error=str(exc))
            raise

        missing_s3_keys = [entry for entry in invoice_audit_log if not entry.get("s3_key")]
        if missing_s3_keys:
            for entry in missing_s3_keys:
                self.logger.error(
                    "invoice_s3_key_missing_after_upload",
                    invoice_id=entry.get("id"),
                    student=entry.get("student"),
                )
        else:
            self.logger.info(
                "invoice_s3_keys_verified",
                invoice_count=len(invoice_audit_log),
            )

        zip_key = self._bundle_invoices(pdf_artifacts)
        status = "completed" if invoices else "skipped"
        message = self._compose_job_message(len(invoices), duplicates)
        metric_label = "succeeded" if invoices else "skipped"
        invoice_jobs_total.labels(status=metric_label).inc()
        self._update_job_record(status=status, message=message, zip_key=zip_key)
        self.logger.info(
            "invoice_agent_complete",
            invoice_count=len(invoices),
            zip_key=zip_key,
            skipped=len(duplicates),
        )
        return {
            "invoice_ids": [invoice.id for invoice in invoices],
            "zip_s3_key": zip_key,
            "duplicates": duplicates,
            "status": status,
            "message": message,
        }

    def _process_student(
        self,
        session: Session,
        student: str,
        student_frame: pd.DataFrame,
        invoice_number: str,
    ) -> tuple[Invoice, InvoicePdf]:
        frame = student_frame.copy()
        frame["Rate"] = frame["Service Code"].map(self.rates).fillna(0)
        frame["Cost"] = frame["Hours"] * frame["Rate"]
        totals = frame[["Hours", "Cost"]].sum().to_dict()

        invoice_code = self.invoice_code or str(uuid4())
        pdf_artifact = generate_invoice_pdf(
            student,
            frame,
            totals,
            self.invoice_date.strftime("%Y-%m-%d"),
            self.service_month_display,
            invoice_code,
            invoice_number,
        )

        invoice = Invoice(
            vendor_id=self.vendor_id,
            student_name=student,
            invoice_number=invoice_number,
            total_hours=float(totals.get("Hours", 0)),
            total_cost=float(totals.get("Cost", 0)),
            invoice_date=self.invoice_date,
            service_month=self.service_month_display,
            invoice_code=invoice_code,
            pdf_s3_key=pdf_artifact.key,
            status="generated",
        )
        session.add(invoice)
        session.flush()

        if pdf_artifact.key:
            invoice.s3_key = pdf_artifact.key
            self.logger.info(
                "invoice_s3_key_saved",
                key=pdf_artifact.key,
                invoice_id=invoice.id,
            )
        else:
            self.logger.warning(
                "missing_s3_key",
                invoice_id=invoice.id,
                student=student,
            )

        for _, row in frame.iterrows():
            line_item = InvoiceLineItem(
                invoice_id=invoice.id,
                student=student,
                clinician=str(row["Employee"]),
                service_code=str(row["Service Code"]),
                hours=float(row["Hours"]),
                rate=float(row["Rate"]),
                cost=float(row["Cost"]),
                service_date=str(row["Schedule Date"]),
            )
            session.add(line_item)

        session.flush()
        return invoice, pdf_artifact

    def _invoice_exists(self, session: Session, invoice_number: str) -> bool:
        """Return True when an invoice number already exists for this vendor."""

        return (
            session.query(Invoice)
            .filter(Invoice.vendor_id == self.vendor_id)
            .filter(Invoice.invoice_number == invoice_number)
            .first()
            is not None
        )

    def _bundle_invoices(self, pdf_artifacts: list[InvoicePdf]) -> str:
        """Create a ZIP archive from generated PDFs and upload it to storage."""

        if not pdf_artifacts:
            return ""

        from io import BytesIO
        from zipfile import ZipFile

        zip_buffer = BytesIO()
        with ZipFile(zip_buffer, "w") as bundle:
            for artifact in pdf_artifacts:
                bundle.writestr(artifact.filename, artifact.content)

        zip_buffer.seek(0)
        bundle_name = f"Invoices_{uuid4()}.zip"
        zip_key = upload_bytes(
            zip_buffer.getvalue(),
            filename=bundle_name,
            content_type="application/zip",
        )
        return zip_key

    @staticmethod
    def _normalize_service_month(
        service_month: str | datetime, invoice_date: datetime
    ) -> tuple[str, datetime]:
        """Return a presentation label and canonical datetime for the service month."""

        if isinstance(service_month, datetime):
            normalized = service_month.replace(day=1)
            return normalized.strftime("%B %Y"), normalized

        candidate = str(service_month or "").strip()
        for fmt in ("%B %Y", "%b %Y"):
            try:
                parsed = datetime.strptime(candidate, fmt)
                return parsed.strftime("%B %Y"), parsed.replace(day=1)
            except ValueError:
                continue

        try:
            parsed_iso = datetime.fromisoformat(candidate)
            normalized = parsed_iso.replace(day=1)
            return normalized.strftime("%B %Y"), normalized
        except ValueError:
            fallback = invoice_date.replace(day=1)
            label = candidate or fallback.strftime("%B %Y")
            return label, fallback

    def _compose_job_message(self, generated_count: int, duplicates: list[str]) -> str:
        """Build a concise message summarizing job outcomes for the dashboard."""

        if generated_count and duplicates:
            skipped_numbers = ", ".join(duplicates)
            return (
                f"Generated {generated_count} invoice(s). Skipped duplicates: {skipped_numbers}."
            )
        if generated_count:
            return f"Generated {generated_count} invoice(s)."
        if duplicates:
            skipped_numbers = ", ".join(duplicates)
            return f"Skipped duplicate invoice(s): {skipped_numbers}."
        return "No invoices were generated."

    def _update_job_record(self, status: str, message: str, zip_key: str) -> None:
        """Persist job metadata after invoice processing completes."""

        if not self.job_id:
            return

        with session_scope() as session:
            job: Job | None = session.get(Job, self.job_id)
            if job is None:
                self.logger.warning("job_record_missing", job_id=self.job_id)
                return

            job.status = status
            job.message = message or None
            job.result_key = zip_key or None
            session.add(job)


__all__ = ["InvoiceAgent", "generate_invoice_number"]
