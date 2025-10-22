"""Production-grade invoice processing agent."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd
import structlog
from sqlalchemy.orm import Session

from app.backend.src.db import session_scope
from app.backend.src.models.invoice import Invoice
from app.backend.src.models.line_item import InvoiceLineItem
from app.backend.src.services.metrics import invoice_jobs_total
from app.backend.src.services.pdf_generation import generate_invoice_pdf
from app.backend.src.services.s3 import upload_file

LOGGER = structlog.get_logger(__name__)

REQUIRED_COLUMNS = ["Client", "Schedule Date", "Hours", "Employee", "Service Code"]


class InvoiceAgent:
    """Automates transformation of uploaded spreadsheets into invoices."""

    def __init__(
        self,
        vendor_id: int,
        invoice_date: datetime,
        service_month: str,
        invoice_code: str | None = None,
        *,
        rates: dict[str, float] | None = None,
    ) -> None:
        self.vendor_id = vendor_id
        self.invoice_date = invoice_date
        self.service_month = service_month
        self.invoice_code = invoice_code or ""
        self.rates = rates or {
            "HHA-SCUSD": 55,
            "LVN-SCUSD": 70,
            "RN-SCUSD": 85,
        }
        self.logger = LOGGER.bind(vendor_id=vendor_id, service_month=service_month)

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
        pdf_paths: list[Path] = []
        self.logger.info("invoice_agent_start", upload=str(file_path))
        try:
            with session_scope() as session:
                for student, student_frame in dataframe.groupby("Client"):
                    invoice, pdf_path = self._process_student(session, student, student_frame)
                    invoices.append(invoice)
                    pdf_paths.append(pdf_path)
        except Exception as exc:
            invoice_jobs_total.labels(status="failed").inc()
            self.logger.error("invoice_agent_error", error=str(exc))
            raise

        zip_key = self._bundle_invoices(pdf_paths)
        invoice_jobs_total.labels(status="succeeded").inc()
        self.logger.info(
            "invoice_agent_complete",
            invoice_count=len(invoices),
            zip_key=zip_key,
        )
        return {
            "invoice_ids": [invoice.id for invoice in invoices],
            "zip_s3_key": zip_key,
        }

    def _process_student(
        self, session: Session, student: str, student_frame: pd.DataFrame
    ) -> tuple[Invoice, Path]:
        frame = student_frame.copy()
        frame["Rate"] = frame["Service Code"].map(self.rates).fillna(0)
        frame["Cost"] = frame["Hours"] * frame["Rate"]
        totals = frame[["Hours", "Cost"]].sum().to_dict()

        invoice_code = self.invoice_code or str(uuid4())
        pdf_path = generate_invoice_pdf(
            student,
            frame,
            totals,
            self.invoice_date.strftime("%Y-%m-%d"),
            self.service_month,
            invoice_code,
        )
        pdf_key = upload_file(pdf_path, content_type="application/pdf")

        invoice = Invoice(
            vendor_id=self.vendor_id,
            student_name=student,
            total_hours=float(totals.get("Hours", 0)),
            total_cost=float(totals.get("Cost", 0)),
            invoice_date=self.invoice_date,
            service_month=self.service_month,
            invoice_code=invoice_code,
            pdf_s3_key=pdf_key,
            status="generated",
        )
        session.add(invoice)
        session.flush()

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
        return invoice, pdf_path

    def _bundle_invoices(self, pdf_paths: list[Path]) -> str:
        """Create a ZIP archive from generated PDFs and upload it to storage."""

        if not pdf_paths:
            return ""

        from tempfile import NamedTemporaryFile
        from zipfile import ZipFile

        with NamedTemporaryFile(suffix=".zip", delete=False) as tmp_file:
            with ZipFile(tmp_file.name, "w") as bundle:
                for pdf_path in pdf_paths:
                    if pdf_path.exists():
                        bundle.write(pdf_path, arcname=pdf_path.name)
            tmp_path = Path(tmp_file.name)

        key = upload_file(tmp_path, content_type="application/zip")
        tmp_path.unlink(missing_ok=True)
        for pdf_path in pdf_paths:
            pdf_path.unlink(missing_ok=True)
        return key


__all__ = ["InvoiceAgent"]
