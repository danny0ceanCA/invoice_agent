"""Vendor-facing API endpoints for dashboards and reporting."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.backend.src.core.security import get_current_user
from app.backend.src.db import get_session_dependency
from app.backend.src.models import Invoice, User, Vendor
from app.backend.src.services.s3 import generate_presigned_url

router = APIRouter(prefix="/vendors", tags=["vendors"])


def _require_vendor(user: User) -> int:
    if user.vendor_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not associated with a vendor",
        )
    return user.vendor_id


def _serialize_invoice(invoice: Invoice) -> dict[str, object | None]:
    return {
        "id": invoice.id,
        "student_name": invoice.student_name,
        "invoice_number": invoice.invoice_number,
        "invoice_code": invoice.invoice_code,
        "service_month": invoice.service_month,
        "invoice_date": invoice.invoice_date.isoformat()
        if invoice.invoice_date
        else None,
        "total_hours": float(invoice.total_hours or 0),
        "total_cost": float(invoice.total_cost or 0),
        "status": invoice.status,
        "pdf_url": generate_presigned_url(invoice.pdf_s3_key)
        if invoice.pdf_s3_key
        else None,
        "line_items": [
            {
                "id": item.id,
                "clinician": item.clinician,
                "service_code": item.service_code,
                "hours": float(item.hours or 0),
                "rate": float(item.rate or 0),
                "cost": float(item.cost or 0),
                "service_date": item.service_date,
            }
            for item in sorted(invoice.line_items, key=lambda entry: entry.service_date)
        ],
    }


@router.get("/me/invoices")
def list_my_invoices(
    session: Session = Depends(get_session_dependency),
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    """Return all invoices and summary metrics for the authenticated vendor."""

    vendor_id = _require_vendor(current_user)
    vendor = session.get(Vendor, vendor_id)
    if vendor is None:
        raise HTTPException(status_code=404, detail="Vendor not found")

    invoices = (
        session.query(Invoice)
        .filter(Invoice.vendor_id == vendor_id)
        .order_by(Invoice.invoice_date.desc(), Invoice.id.desc())
        .all()
    )

    total_cost = sum(float(invoice.total_cost or 0) for invoice in invoices)
    total_hours = sum(float(invoice.total_hours or 0) for invoice in invoices)
    student_names = {invoice.student_name for invoice in invoices}
    latest_date = None
    for invoice in invoices:
        if invoice.invoice_date and (
            latest_date is None or invoice.invoice_date > latest_date
        ):
            latest_date = invoice.invoice_date

    summary = {
        "invoice_count": len(invoices),
        "total_cost": total_cost,
        "total_hours": total_hours,
        "students_served": len(student_names),
        "latest_invoice_date": latest_date.isoformat() if latest_date else None,
    }

    return {
        "vendor": {
            "id": vendor.id,
            "name": vendor.name,
            "contact_email": vendor.contact_email,
        },
        "summary": summary,
        "invoices": [_serialize_invoice(invoice) for invoice in invoices],
    }


__all__ = ["router"]
