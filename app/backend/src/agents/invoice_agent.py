"""Invoice processing agent and helpers."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Mapping

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.backend.src.models.invoice import Invoice
from app.backend.src.models.job import Job
from app.backend.src.services.pdf_generation import generate_invoice_pdf
from app.backend.src.services.storage import upload_file

LOGGER = logging.getLogger(__name__)


def generate_invoice_number(student_name: str, service_month: datetime) -> str:
    """Return a deterministic invoice number for the student and month."""

    parts = re.split(r"\s+", student_name.strip())
    last_name = parts[-1].capitalize() if parts else "Unknown"
    month_token = service_month.strftime("%b").upper()
    year_token = service_month.strftime("%Y")
    return f"{last_name}-{month_token}{year_token}"


@dataclass(slots=True)
class InvoiceAgent:
    """Process uploaded timesheets into invoices."""

    session: Session
    vendor_id: int
    service_month: datetime
    invoice_date: date | None
    invoice_code: str = "STANDARD"
    rates: Mapping[str, float] = field(default_factory=dict)

    def run(self, file_path: Path, filename: str) -> dict[str, int]:
        """Generate invoices for the uploaded file."""

        df = pd.read_csv(file_path)
        if "Client" not in df.columns or "Hours" not in df.columns:
            raise ValueError("Uploaded file must contain 'Client' and 'Hours' columns")

        df["Client"] = df["Client"].astype(str).str.strip()
        df["Hours"] = pd.to_numeric(df["Hours"], errors="coerce").fillna(0.0)

        if "Rate" in df.columns:
            df["Rate"] = pd.to_numeric(df["Rate"], errors="coerce").fillna(0.0)
        else:
            lookup = pd.Series(self.rates)
            if "Service Code" in df.columns:
                df["Rate"] = df["Service Code"].map(lookup).fillna(0.0)
            else:
                df["Rate"] = 0.0

        df["Cost"] = df["Hours"] * df["Rate"]

        created = 0
        skipped = 0

        try:
            for student, group in df.groupby("Client"):
                invoice_number = generate_invoice_number(student, self.service_month)

                existing_invoice = self.session.execute(
                    select(Invoice).where(
                        Invoice.vendor_id == self.vendor_id,
                        Invoice.invoice_number == invoice_number,
                    )
                ).scalar_one_or_none()

                if existing_invoice:
                    job = Job(
                        vendor_id=self.vendor_id,
                        filename=filename,
                        status="skipped",
                        message=f"Skipped duplicate invoice: {invoice_number}",
                    )
                    self.session.add(job)
                    skipped += 1
                    LOGGER.warning("Duplicate invoice skipped: %s", invoice_number)
                    continue

                totals = {
                    "Hours": float(group["Hours"].sum()),
                    "Cost": float(group["Cost"].sum()),
                }

                pdf_path = generate_invoice_pdf(
                    student,
                    group,
                    totals,
                    self.invoice_date,
                    self.service_month,
                    self.invoice_code,
                    invoice_number,
                )
                storage_key = upload_file(pdf_path)

                invoice = Invoice(
                    vendor_id=self.vendor_id,
                    student_name=student,
                    invoice_number=invoice_number,
                    total_hours=Decimal(str(totals["Hours"])),
                    total_cost=Decimal(str(totals["Cost"])),
                    invoice_date=self.invoice_date,
                    service_month=self.service_month.strftime("%B %Y"),
                    pdf_s3_key=storage_key,
                )
                self.session.add(invoice)
                self.session.flush()

                job = Job(
                    vendor_id=self.vendor_id,
                    invoice_id=invoice.id,
                    filename=filename,
                    status="completed",
                    message=f"Invoice generated: {invoice_number}",
                )
                self.session.add(job)
                created += 1
                LOGGER.info("Invoice generated: %s", invoice_number)

            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

        return {"created": created, "skipped": skipped, "total": created + skipped}
