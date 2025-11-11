"""District profile and district console schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from .address import PostalAddress, PostalAddressInput


class DistrictProfile(BaseModel):
    """Serialized district profile details for the portal."""

    id: int
    company_name: str
    contact_name: str | None
    contact_email: EmailStr | None
    phone_number: str | None
    mailing_address: PostalAddress | None
    district_key: str
    is_profile_complete: bool

    model_config = ConfigDict(from_attributes=True)


class DistrictProfileUpdateNormalized(BaseModel):
    """Normalized district profile update payload."""

    company_name: str
    contact_name: str
    contact_email: EmailStr
    phone_number: str
    mailing_address: PostalAddress


class DistrictProfileUpdate(BaseModel):
    """Payload for updating district profile information."""

    company_name: str
    contact_name: str
    contact_email: EmailStr
    phone_number: str
    mailing_address: PostalAddressInput

    def normalized(self) -> DistrictProfileUpdateNormalized:
        """Return a copy of the payload with trimmed fields."""

        normalized_address = self.mailing_address.normalized()

        return DistrictProfileUpdateNormalized(
            company_name=self.company_name.strip(),
            contact_name=self.contact_name.strip(),
            contact_email=self.contact_email,
            phone_number=self.phone_number.strip(),
            mailing_address=normalized_address,
        )


class DistrictMembershipEntry(BaseModel):
    """Serialized membership entry for a district user."""

    district_id: int
    company_name: str
    district_key: str
    is_active: bool


class DistrictMembershipCollection(BaseModel):
    """List of district memberships paired with the active selection."""

    active_district_id: int | None
    memberships: list[DistrictMembershipEntry]


class DistrictKeySubmission(BaseModel):
    """Payload submitted when a user enters a district access key."""

    district_key: str

    def normalized(self) -> "DistrictKeySubmission":
        """Return a copy with a normalized district key."""

        key_characters = "".join(char for char in self.district_key if char.isalnum()).upper()
        normalized_key = (
            "-".join(
                key_characters[i : i + 4] for i in range(0, len(key_characters), 4)
            )
            if key_characters
            else ""
        )
        return DistrictKeySubmission(district_key=normalized_key)


class DistrictVendorInvoiceStudent(BaseModel):
    """Student service summary attached to an invoice."""

    id: int
    name: str
    service: str | None
    amount: float
    pdf_url: str | None = None
    pdf_s3_key: str | None = None
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
    download_url: str | None
    pdf_url: str | None
    pdf_s3_key: str | None = None
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
    remit_to_address: PostalAddress | None
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
    "DistrictProfileUpdateNormalized",
    "DistrictMembershipCollection",
    "DistrictMembershipEntry",
    "DistrictKeySubmission",
    "DistrictVendorInvoice",
    "DistrictVendorInvoiceStudent",
    "DistrictVendorLatestInvoice",
    "DistrictVendorMetrics",
    "DistrictVendorOverview",
    "DistrictVendorProfile",
]
