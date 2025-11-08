"""Services for assembling district-facing vendor data."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from sqlalchemy.orm import Session, selectinload

from app.backend.src.models import Invoice, Vendor
from app.backend.src.schemas.district import (
    DistrictVendorInvoice,
    DistrictVendorInvoiceStudent,
    DistrictVendorLatestInvoice,
    DistrictVendorMetrics,
    DistrictVendorOverview,
    DistrictVendorProfile,
)

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

    vendors = (
        session.query(Vendor)
        .filter(Vendor.district_id == district_id)
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
        flat_invoices: list[DistrictVendorInvoice] = []

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

            entry = DistrictVendorInvoice(
                id=invoice.id,
                month=month,
                month_index=month_index,
                year=year,
                status=(invoice.status or "").strip(),
                total=float(invoice.total_cost or 0),
                processed_on=_format_processed_on(invoice_date),
                pdf_url=None,
                timesheet_csv_url=None,
                students=students,
            )

            invoices_by_year[year].append(entry)
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
        if invoice_models:
            latest = invoice_models[0]
            latest_month_name, latest_service_year = _extract_service_month(
                latest.service_month
            )
            latest_date = latest.invoice_date
            latest_month = (
                latest_date.strftime("%B")
                if latest_date
                else latest_month_name
                or "Unknown"
            )
            latest_year_value = (
                latest_date.year if latest_date else latest_service_year or datetime.utcnow().year
            )
            latest_invoice_summary = DistrictVendorLatestInvoice(
                month=latest_month,
                year=latest_year_value,
                total=float(latest.total_cost or 0),
                status=(latest.status or "").strip(),
            )

        profile = DistrictVendorProfile(
            id=vendor.id,
            name=vendor.company_name,
            contact_name=vendor.contact_name,
            contact_email=vendor.contact_email,
            phone_number=vendor.phone_number,
            remit_to_address=vendor.remit_to_address,
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


__all__ = ["fetch_district_vendor_overview"]
