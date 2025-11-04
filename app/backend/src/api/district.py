"""District-facing reporting endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.backend.src.core.security import get_current_user
from app.backend.src.db import get_session_dependency
from app.backend.src.models import Invoice, User, Vendor
from app.backend.src.services.s3 import generate_presigned_url

router = APIRouter(prefix="/district", tags=["district"])


def _require_district_access(user: User) -> None:
    if user.role not in {"admin", "district"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not authorized for district reporting",
        )


@router.get("/vendors")
def list_vendor_overview(
    session: Session = Depends(get_session_dependency),
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    """Return aggregated invoice metrics for every vendor."""

    _require_district_access(current_user)

    vendors = session.query(Vendor).order_by(Vendor.name).all()
    all_invoices = (
        session.query(Invoice)
        .order_by(Invoice.invoice_date.desc(), Invoice.id.desc())
        .all()
    )

    invoices_by_vendor: dict[int, list[Invoice]] = {}
    for invoice in all_invoices:
        invoices_by_vendor.setdefault(invoice.vendor_id, []).append(invoice)

    vendor_payload: list[dict[str, object | None]] = []
    total_cost = 0.0
    total_hours = 0.0
    invoice_count = 0

    for vendor in vendors:
        vendor_invoices = invoices_by_vendor.get(vendor.id, [])
        vendor_cost = sum(float(entry.total_cost or 0) for entry in vendor_invoices)
        vendor_hours = sum(float(entry.total_hours or 0) for entry in vendor_invoices)
        vendor_students = {entry.student_name for entry in vendor_invoices}
        latest_invoice = vendor_invoices[0] if vendor_invoices else None

        vendor_payload.append(
            {
                "id": vendor.id,
                "name": vendor.name,
                "contact_email": vendor.contact_email,
                "invoice_count": len(vendor_invoices),
                "total_cost": vendor_cost,
                "total_hours": vendor_hours,
                "students_served": len(vendor_students),
                "latest_invoice": None
                if latest_invoice is None
                else {
                    "invoice_number": latest_invoice.invoice_number,
                    "service_month": latest_invoice.service_month,
                    "invoice_date": latest_invoice.invoice_date.isoformat()
                    if latest_invoice.invoice_date
                    else None,
                    "status": latest_invoice.status,
                    "total_cost": float(latest_invoice.total_cost or 0),
                    "total_hours": float(latest_invoice.total_hours or 0),
                    "student_name": latest_invoice.student_name,
                    "pdf_url": generate_presigned_url(latest_invoice.pdf_s3_key)
                    if latest_invoice.pdf_s3_key
                    else None,
                },
            }
        )

        total_cost += vendor_cost
        total_hours += vendor_hours
        invoice_count += len(vendor_invoices)

    return {
        "totals": {
            "vendors": len(vendors),
            "invoice_count": invoice_count,
            "total_cost": total_cost,
            "total_hours": total_hours,
        },
        "vendors": vendor_payload,
    }


__all__ = ["router"]
