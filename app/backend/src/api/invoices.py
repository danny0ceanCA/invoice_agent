"""Invoice related endpoints."""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.backend.src.agents.invoice_agent import InvoiceAgent
from app.backend.src.core.db import get_db
from app.backend.src.models.invoice import Invoice
from app.backend.src.schemas.invoice import InvoiceSummary

router = APIRouter(prefix="/invoices", tags=["invoices"])


@router.get("", response_model=list[InvoiceSummary])
async def list_invoices(session: Session = Depends(get_db)) -> list[InvoiceSummary]:
    """Return a list of generated invoices."""

    invoices = (
        session.execute(select(Invoice).order_by(Invoice.created_at.desc()))
        .scalars()
        .all()
    )
    return [
        InvoiceSummary(
            id=invoice.id,
            vendor_id=invoice.vendor_id,
            student_name=invoice.student_name,
            invoice_number=invoice.invoice_number,
            service_month=invoice.service_month,
        )
        for invoice in invoices
    ]


@router.post("/upload")
async def upload_invoice(
    *,
    file: UploadFile = File(...),
    vendor_id: int = Form(...),
    invoice_date: str | None = Form(None),
    service_month: str = Form(...),
    session: Session = Depends(get_db),
) -> dict[str, int]:
    """Process an uploaded timesheet file and generate invoices."""

    try:
        service_month_dt = datetime.strptime(service_month, "%B %Y")
    except ValueError as exc:  # pragma: no cover - defensive branch
        raise HTTPException(status_code=400, detail="Invalid service_month format. Use 'Month YYYY'.") from exc

    parsed_invoice_date = None
    if invoice_date:
        try:
            parsed_invoice_date = datetime.strptime(invoice_date, "%Y-%m-%d").date()
        except ValueError as exc:  # pragma: no cover - defensive branch
            raise HTTPException(status_code=400, detail="Invalid invoice_date format. Use YYYY-MM-DD.") from exc

    suffix = Path(file.filename or "invoice.csv").suffix or ".csv"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
        contents = await file.read()
        tmp_file.write(contents)
        tmp_path = Path(tmp_file.name)

    try:
        agent = InvoiceAgent(
            session=session,
            vendor_id=vendor_id,
            service_month=service_month_dt,
            invoice_date=parsed_invoice_date,
        )
        return agent.run(tmp_path, file.filename or tmp_path.name)
    finally:
        tmp_path.unlink(missing_ok=True)


@router.get("/{invoice_id}/pdf")
async def download_invoice(invoice_id: int, session: Session = Depends(get_db)) -> FileResponse:
    """Return the generated PDF for an invoice."""

    invoice = session.get(Invoice, invoice_id)
    if invoice is None or invoice.pdf_s3_key is None:
        raise HTTPException(status_code=404, detail="Invoice not found")

    file_path = Path(invoice.pdf_s3_key)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Invoice artifact missing")

    return FileResponse(file_path, media_type="application/pdf", filename=file_path.name)
