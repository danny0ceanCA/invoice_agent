"""Services for assembling district-facing vendor data."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

import structlog
from sqlalchemy.orm import Session, selectinload

from app.backend.src.models import District, Invoice, Vendor
from app.backend.src.schemas.address import PostalAddress, build_postal_address
from app.backend.src.schemas.district import (
    DistrictVendorInvoice,
    DistrictVendorInvoiceStudent,
    DistrictVendorLatestInvoice,
    DistrictVendorMetrics,
    DistrictVendorOverview,
    DistrictVendorProfile,
)
from app.backend.src.services.s3 import generate_presigned_url

LOGGER = structlog.get_logger(__name__)

MONTH_ORDER = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]
MONTH_INDEX = {month: index for index, month in enumerate(MONTH_ORDER)}


def _extract_service_month(service_month: str | None) -> tuple[str | None, int | None]:
    """Return the month name and year parsed from a service month string."""

    if not service_month:
        return None, None
    parts = service_month.split()
    if len(parts) >= 2 and parts[0] in MONTH_INDEX and parts[1].isdigit():
        return parts[0], int(parts[1])
    return service_month, None


def _format_processed_on(invoice_date: datetime | None) -> str | None:
    """Format the processed-on date for display."""

    if not invoice_date:
        return None
    return invoice_date.strftime("%b %d, %Y").replace(" 0", " ")


def _is_approved_status(status: str) -> bool:
    """Return True when the status represents an approved invoice."""

    normalized = status.lower()
    return "approved" in normalized or "paid" in normalized


def fetch_district_vendor_overview(
    session: Session, district_id: int
) -> DistrictVendorOverview:
    """Return vendor data ready for district consumption."""

    district = session.get(District, district_id)
    if district is None or not district.district_key:
        return DistrictVendorOverview(
            generated_at=datetime.utcnow(),
            vendors=[],
        )

    vendors = (
        session.query(Vendor)
        .filter(Vendor.district_key == district.district_key)
        .options(selectinload(Vendor.invoices).selectinload(Invoice.line_items))
        .order_by(Vendor.company_name.asc())
        .all()
    )

    profiles: list[DistrictVendorProfile] = []
    for vendor in vendors:
        invoice_models = sorted(
            vendor.invoices,
            key=lambda invoice: (
                invoice.invoice_date or invoice.created_at or datetime.min
            ),
            reverse=True,
        )

        invoices_by_year: dict[int, list[DistrictVendorInvoice]] = defaultdict(list)
        monthly_groups: dict[tuple[int, str], dict[str, Any]] = {}

        for invoice in invoice_models:
            month_name, service_year = _extract_service_month(invoice.service_month)
            invoice_date = invoice.invoice_date
            if invoice_date:
                year = invoice_date.year
                month = invoice_date.strftime("%B")
                month_index = MONTH_INDEX.get(month)
            else:
                year = service_year or datetime.utcnow().year
                month = month_name or "Unknown"
                month_index = MONTH_INDEX.get(month_name or "")

            students = [
                DistrictVendorInvoiceStudent(
                    id=item.id,
                    name=item.student,
                    service=item.service_code,
                    amount=float(item.cost or 0),
                )
                for item in invoice.line_items
            ]

            if not invoice.pdf_s3_key:
                LOGGER.warning(
                    "missing_s3_key",
                    invoice_id=invoice.id,
                    student=invoice.student_name,
                    vendor_id=vendor.id,
                )

            status_value = (invoice.status or "").strip()
            processed_on = _format_processed_on(invoice_date)
            group_key = (year, month)
            existing = monthly_groups.get(group_key)
            download_name = invoice.invoice_number or invoice.student_name or "invoice"
            download_name = download_name.strip() or "invoice"
            if not download_name.lower().endswith(".pdf"):
                download_name = f"{download_name}.pdf"
            if existing is None:
                monthly_groups[group_key] = {
                    "id": invoice.id,
                    "month": month,
                    "month_index": month_index,
                    "year": year,
                    "total": float(invoice.total_cost or 0),
                    "processed_on": processed_on,
                    "latest_invoice_date": invoice_date,
                    "status_values": {status_value} if status_value else set(),
                    "students": list(students),
                    "pdf_s3_key": invoice.pdf_s3_key,
                    "download_name": download_name,
                }
            else:
                existing["total"] = float(existing["total"]) + float(
                    invoice.total_cost or 0
                )
                existing_students = existing["students"]
                existing_students.extend(students)
                if month_index is not None and existing["month_index"] is None:
                    existing["month_index"] = month_index
                if status_value:
                    status_values = existing["status_values"]
                    status_values.add(status_value)
                if (
                    invoice_date
                    and (
                        existing["latest_invoice_date"] is None
                        or invoice_date > existing["latest_invoice_date"]
                    )
                ):
                    existing["latest_invoice_date"] = invoice_date
                    existing["processed_on"] = processed_on
                    existing["pdf_s3_key"] = invoice.pdf_s3_key
                    existing["download_name"] = download_name
                if invoice.id < existing["id"]:
                    existing["id"] = invoice.id

        flat_invoices: list[DistrictVendorInvoice] = []
        for data in monthly_groups.values():
            status_values = data["status_values"]
            if not status_values:
                status_label = ""
            elif len(status_values) == 1:
                status_label = next(iter(status_values))
            else:
                status_label = "Mixed"

            download_url = _build_presigned_url(
                data.get("pdf_s3_key"), data.get("download_name"), int(data["id"])
            )

            entry = DistrictVendorInvoice(
                id=int(data["id"]),
                month=data["month"],
                month_index=data["month_index"],
                year=int(data["year"]),
                status=status_label,
                total=float(data["total"]),
                processed_on=data["processed_on"],
                download_url=download_url,
                pdf_url=download_url,
                timesheet_csv_url=None,
                students=data["students"],
            )

            invoices_by_year[entry.year].append(entry)
            flat_invoices.append(entry)

        for year, entries in invoices_by_year.items():
            invoices_by_year[year] = sorted(
                entries,
                key=lambda entry: entry.month_index if entry.month_index is not None else -1,
                reverse=True,
            )

        latest_year = max((invoice.year for invoice in flat_invoices), default=None)
        invoices_this_year = [
            invoice for invoice in flat_invoices if latest_year is not None and invoice.year == latest_year
        ]
        approved_invoices = [
            invoice for invoice in invoices_this_year if _is_approved_status(invoice.status)
        ]
        needs_action_invoices = [
            invoice for invoice in invoices_this_year if invoice not in approved_invoices
        ]
        total_spend = sum(invoice.total for invoice in invoices_this_year)
        outstanding_spend = sum(invoice.total for invoice in needs_action_invoices)

        if invoices_this_year:
            health_label = "Needs Attention" if outstanding_spend > 0 else "On Track"
        elif flat_invoices:
            health_label = "Monitoring"
        else:
            health_label = "Onboarding"

        latest_invoice_summary = None
        if flat_invoices:
            latest_invoice_entry = max(
                flat_invoices,
                key=lambda entry: (
                    entry.year,
                    entry.month_index if entry.month_index is not None else -1,
                ),
            )
            latest_status = latest_invoice_entry.status or "Processing"
            latest_invoice_summary = DistrictVendorLatestInvoice(
                month=latest_invoice_entry.month,
                year=latest_invoice_entry.year,
                total=latest_invoice_entry.total,
                status=latest_status,
            )

        profile = DistrictVendorProfile(
            id=vendor.id,
            name=vendor.company_name,
            contact_name=vendor.contact_name,
            contact_email=vendor.contact_email,
            phone_number=vendor.phone_number,
            remit_to_address=_build_vendor_address(vendor),
            metrics=DistrictVendorMetrics(
                latest_year=latest_year,
                invoices_this_year=len(invoices_this_year),
                approved_count=len(approved_invoices),
                needs_action_count=len(needs_action_invoices),
                total_spend=total_spend,
                outstanding_spend=outstanding_spend,
            ),
            health_label=health_label,
            latest_invoice=latest_invoice_summary,
            invoices=dict(invoices_by_year),
        )
        profiles.append(profile)

    return DistrictVendorOverview(
        generated_at=datetime.utcnow(),
        vendors=profiles,
    )


def _build_vendor_address(vendor: Vendor) -> PostalAddress | None:
    """Return the vendor remit-to address as a structured object."""

    return build_postal_address(
        vendor.remit_to_street,
        vendor.remit_to_city,
        vendor.remit_to_state,
        vendor.remit_to_postal_code,
    )


def _build_presigned_url(
    key: str | None, download_name: str | None, invoice_id: int
) -> str | None:
    """Return a presigned URL for an invoice PDF if the key is available."""

    if not key:
        return None

    safe_name = (download_name or "invoice.pdf").strip() or "invoice.pdf"

    try:
        return generate_presigned_url(
            key,
            download_name=safe_name,
            response_content_type="application/pdf",
        )
    except Exception as exc:  # pragma: no cover - logging best effort
        LOGGER.warning(
            "invoice_presign_failed",
            key=key,
            invoice_id=invoice_id,
            error=str(exc),
        )
        return None


__all__ = ["fetch_district_vendor_overview"]
