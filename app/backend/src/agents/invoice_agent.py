"""Production-grade invoice processing agent."""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd
import structlog
from sqlalchemy.orm import Session

from ..db import session_scope
from ..models import Clinician, Invoice, InvoiceLineItem, Job, Student, Vendor
from ..services.metrics import invoice_jobs_total
from ..services.pdf_generation import InvoicePdf, generate_invoice_pdf
from ..services.s3 import sanitize_company_name, upload_bytes

LOGGER = structlog.get_logger(__name__)

REQUIRED_COLUMNS = ["Client", "Schedule Date", "Hours", "Employee", "Service Code"]


def _split_name(full_name: str) -> tuple[str, str]:
    """
    Naive name splitter: last token becomes last_name, everything before is first_name.
    Safe enough for now and can be refined later.
    """

    parts = (full_name or "").strip().split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return " ".join(parts[:-1]), parts[-1]


def _generate_student_key(session: Session, district_key: str) -> str:
    """
    Generate a new student_key like SK-00000001, scoped per district_key.
    Uses the highest existing ID for that district as a simple sequence base.
    """

    last_student = (
        session.query(Student)
        .filter(Student.district_key == district_key)
        .order_by(Student.id.desc())
        .first()
    )
    seq = (last_student.id if last_student else 0) + 1
    return f"SK-{seq:08d}"


def _get_or_create_student(
    session: Session,
    district_key: str,
    raw_name: str,
) -> int | None:
    """
    Ensure a Student row exists for the given district_key + full_name, and return its ID.
    Does not backfill or alter existing invoices; used only for new invoice processing.
    """

    raw_name = (raw_name or "").strip()
    if not raw_name:
        return None

    student = (
        session.query(Student)
        .filter_by(district_key=district_key, full_name=raw_name)
        .one_or_none()
    )
    if student is not None:
        return student.id

    first_name, last_name = _split_name(raw_name)
    student_key = _generate_student_key(session, district_key)

    student = Student(
        district_key=district_key,
        student_key=student_key,
        first_name=first_name,
        last_name=last_name,
        full_name=raw_name,
    )
    session.add(student)
    session.flush()  # assigns student.id

    return student.id


def _extract_license_from_service_code(
    service_code: str | None,
) -> tuple[str | None, str | None]:
    """
    Given service_code like 'HHA-SCUSD' or 'LVN-SCUSD', return (license_code, license_title).
    """

    if not service_code:
        return None, None

    head = service_code.split("-", 1)[0].strip().upper()
    if not head:
        return None, None

    if head == "HHA":
        return "HHA", "Health Aide"
    if head == "LVN":
        return "LVN", "Licensed Vocational Nurse"

    # Unknown or other codes: keep the code, no title
    return head, None


def _get_or_create_clinician(
    session: Session,
    district_key: str,
    raw_name: str,
    service_code: str | None = None,
) -> int | None:
    """
    Ensure a Clinician row exists for the given district_key + full_name, and return its ID.
    Uses service_code to populate license_code/license_title when available.
    """

    raw_name = (raw_name or "").strip()
    if not raw_name:
        return None

    clinician = (
        session.query(Clinician)
        .filter_by(district_key=district_key, full_name=raw_name)
        .one_or_none()
    )

    license_code = license_title = None
    if service_code:
        license_code, license_title = _extract_license_from_service_code(service_code)

    if clinician is None:
        first_name, last_name = _split_name(raw_name)
        clinician = Clinician(
            district_key=district_key,
            first_name=first_name,
            last_name=last_name,
            full_name=raw_name,
            license_code=license_code,
            license_title=license_title,
        )
        session.add(clinician)
        session.flush()
        return clinician.id

    updated = False
    if license_code and not clinician.license_code:
        clinician.license_code = license_code
        updated = True
    if license_title and not clinician.license_title:
        clinician.license_title = license_title
        updated = True
    if updated:
        session.add(clinician)

    return clinician.id


def generate_invoice_number(student_name: str, service_month: datetime | date) -> str:
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
        invoice_date: datetime | date,
        service_month: str | datetime | date,
        invoice_code: str | None = None,
        *,
        job_id: str | None = None,
        rates: dict[str, float] | None = None,
    ) -> None:
        self.vendor_id = vendor_id
        self.invoice_date = (
            invoice_date.date() if isinstance(invoice_date, datetime) else invoice_date
        )
        (
            self.service_month_display,
            self.service_month_date,
            self.service_month_name,
            self.service_year,
            self.service_month_num,
        ) = self._normalize_service_month(service_month, self.invoice_date)
        self.invoice_code = invoice_code or ""
        self.job_id = job_id
        self.rates = rates or {
            "HHA-SCUSD": 55,
            "LVN-SCUSD": 70,
            "RN-SCUSD": 85,
        }
        self.vendor: Vendor | None = None
        self.vendor_company_name: str | None = None
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
                vendor = self._get_vendor(session)
                vendor_name = self._ensure_vendor_company_name(session, vendor)
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
                        session,
                        student,
                        student_frame,
                        invoice_number,
                        vendor_name,
                        vendor,
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

        keys = [entry["s3_key"] for entry in invoice_audit_log if entry.get("s3_key")]
        if len(keys) != len(set(keys)):
            self.logger.warning(
                "duplicate_invoice_keys_detected",
                duplicate_count=len(keys) - len(set(keys)),
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
        vendor_company_name: str,
        vendor: Vendor,
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
            company_name=vendor_company_name,
            reference_date=self.service_month_date,
        )

        invoice = Invoice(
            vendor_id=self.vendor_id,
            student_name=student,
            invoice_number=invoice_number,
            total_hours=float(totals.get("Hours", 0)),
            total_cost=float(totals.get("Cost", 0)),
            invoice_date=self.invoice_date,
            service_month=self.service_month_name,
            service_year=self.service_year,
            service_month_num=self.service_month_num,
            district_key=vendor.district_key,
            invoice_code=invoice_code,
            vendor_name_snapshot=vendor.company_name,
            pdf_s3_key=pdf_artifact.key,
            status="generated",
        )
        session.add(invoice)
        session.flush()

        _get_or_create_student(
            session=session,
            district_key=invoice.district_key,
            raw_name=invoice.student_name,
        )

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
            _get_or_create_clinician(
                session=session,
                district_key=invoice.district_key,
                raw_name=str(row["Employee"]),
                service_code=str(row["Service Code"]),
            )
            line_item = InvoiceLineItem(
                invoice_id=invoice.id,
                invoice_number=invoice.invoice_number,
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
        reference_date = self.service_month_date
        safe_company = sanitize_company_name(self.vendor_company_name)
        bundle_name = (
            f"{safe_company}_{reference_date.year:04d}_{reference_date.month:02d}_invoices.zip"
        )
        zip_key = upload_bytes(
            zip_buffer.getvalue(),
            filename=bundle_name,
            content_type="application/zip",
            company_name=self.vendor_company_name,
            reference_date=reference_date,
        )
        return zip_key

    def _get_vendor(self, session: Session) -> Vendor:
        """Return the vendor instance, caching it for repeated access."""

        if self.vendor is None:
            vendor = session.get(Vendor, self.vendor_id)
            if vendor is None:
                raise ValueError(f"Vendor {self.vendor_id} not found")
            self.vendor = vendor
        return self.vendor

    def _ensure_vendor_company_name(
        self, session: Session, vendor: Vendor | None = None
    ) -> str:
        """Resolve and cache the vendor company name for S3 key generation."""

        if self.vendor_company_name:
            return self.vendor_company_name

        vendor = vendor or self._get_vendor(session)
        if vendor and vendor.company_name:
            self.vendor_company_name = vendor.company_name
        else:
            fallback = f"vendor-{self.vendor_id}"
            self.vendor_company_name = fallback
            self.logger.warning(
                "vendor_company_missing",
                vendor_id=self.vendor_id,
                fallback=self.vendor_company_name,
            )
        return self.vendor_company_name

    @staticmethod
    def _normalize_service_month(
        service_month: str | datetime | date, invoice_date: date
    ) -> tuple[str, date, str, int, int]:
        """Return normalized fields for the service month."""

        fallback_year = invoice_date.year

        if isinstance(service_month, datetime):
            normalized_date = service_month.date().replace(day=1)
            month_name = normalized_date.strftime("%B")
            return (
                normalized_date.strftime("%B %Y"),
                normalized_date,
                month_name.lower(),
                normalized_date.year,
                normalized_date.month,
            )

        if isinstance(service_month, date):
            normalized_date = service_month.replace(day=1)
            month_name = normalized_date.strftime("%B")
            return (
                normalized_date.strftime("%B %Y"),
                normalized_date,
                month_name.lower(),
                normalized_date.year,
                normalized_date.month,
            )

        candidate = str(service_month or "").strip()

        def _build_from_parts(month: int, year: int, label: str | None = None) -> tuple[str, date, str, int, int]:
            normalized_date = date(year, month, 1)
            month_name = normalized_date.strftime("%B")
            label_value = label or f"{month_name} {year}"
            return label_value, normalized_date, month_name.lower(), year, month

        for fmt in ("%B %Y", "%b %Y", "%Y-%m-%d", "%Y-%m"):
            try:
                parsed = datetime.strptime(candidate, fmt)
                label = parsed.strftime("%B %Y")
                return _build_from_parts(parsed.month, parsed.year, label)
            except ValueError:
                continue

        for fmt in ("%B", "%b"):
            try:
                parsed = datetime.strptime(candidate, fmt)
                month = parsed.month
                label = f"{parsed.strftime('%B')} {fallback_year}"
                return _build_from_parts(month, fallback_year, label)
            except ValueError:
                continue

        if candidate:
            try:
                parsed_iso = datetime.fromisoformat(candidate)
                label = parsed_iso.strftime("%B %Y")
                return _build_from_parts(parsed_iso.month, parsed_iso.year, label)
            except ValueError:
                pass

        fallback = invoice_date.replace(day=1)
        return _build_from_parts(fallback.month, fallback.year, candidate or None)

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
