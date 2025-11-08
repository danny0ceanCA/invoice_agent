"""District profile and district console schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class DistrictProfile(BaseModel):
    """Serialized district profile details for the portal."""

    id: int
    company_name: str
    contact_name: str | None
    contact_email: EmailStr | None
    phone_number: str | None
    mailing_address: str | None
    is_profile_complete: bool

    model_config = ConfigDict(from_attributes=True)


class DistrictProfileUpdate(BaseModel):
    """Payload for updating district profile information."""

    company_name: str
    contact_name: str
    contact_email: EmailStr
    phone_number: str
    mailing_address: str

    def normalized(self) -> "DistrictProfileUpdate":
        """Return a copy of the payload with trimmed fields."""

        return DistrictProfileUpdate(
            company_name=self.company_name.strip(),
            contact_name=self.contact_name.strip(),
            contact_email=self.contact_email,
            phone_number=self.phone_number.strip(),
            mailing_address=self.mailing_address.strip(),
        )


class DistrictVendorInvoiceStudent(BaseModel):
    """Student service summary attached to an invoice."""

    id: int
    name: str
    service: str | None
    amount: float
    pdf_url: str | None = None
    timesheet_url: str | None = None


class DistrictVendorInvoice(BaseModel):
    """Summarized vendor invoice for district review."""

    id: int
    month: str
    month_index: int | None
    year: int
    status: str
    total: float
    processed_on: str | None
    pdf_url: str | None
    timesheet_csv_url: str | None
    students: list[DistrictVendorInvoiceStudent]


class DistrictVendorMetrics(BaseModel):
    """Aggregate vendor metrics used throughout the console."""

    latest_year: int | None
    invoices_this_year: int
    approved_count: int
    needs_action_count: int
    total_spend: float
    outstanding_spend: float


class DistrictVendorLatestInvoice(BaseModel):
    """Details about the latest invoice on file for a vendor."""

    month: str
    year: int
    total: float
    status: str


class DistrictVendorProfile(BaseModel):
    """Vendor data surfaced within the district console."""

    id: int
    name: str
    contact_name: str | None
    contact_email: EmailStr | None
    phone_number: str | None
    remit_to_address: str | None
    metrics: DistrictVendorMetrics
    health_label: str | None
    latest_invoice: DistrictVendorLatestInvoice | None
    invoices: dict[int, list[DistrictVendorInvoice]]


class DistrictVendorOverview(BaseModel):
    """Collection of vendor profiles for district consumption."""

    generated_at: datetime
    vendors: list[DistrictVendorProfile]


__all__ = [
    "DistrictProfile",
    "DistrictProfileUpdate",
    "DistrictVendorInvoice",
    "DistrictVendorInvoiceStudent",
    "DistrictVendorLatestInvoice",
    "DistrictVendorMetrics",
    "DistrictVendorOverview",
    "DistrictVendorProfile",
]
