"""Vendor schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr


class VendorProfile(BaseModel):
    """Serialized vendor profile details for the portal."""

    id: int
    company_name: str
    contact_name: str | None
    contact_email: EmailStr | None
    phone_number: str | None
    remit_to_address: str | None
    is_profile_complete: bool

    model_config = ConfigDict(from_attributes=True)


class VendorProfileUpdate(BaseModel):
    """Payload for updating vendor profile information."""

    company_name: str
    contact_name: str
    contact_email: EmailStr
    phone_number: str
    remit_to_address: str

    def normalized(self) -> "VendorProfileUpdate":
        """Return a copy of the payload with trimmed fields."""

        return VendorProfileUpdate(
            company_name=self.company_name.strip(),
            contact_name=self.contact_name.strip(),
            contact_email=self.contact_email,
            phone_number=self.phone_number.strip(),
            remit_to_address=self.remit_to_address.strip(),
        )
