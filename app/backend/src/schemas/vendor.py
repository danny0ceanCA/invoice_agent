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
    district_company_name: str | None
    is_district_linked: bool

    model_config = ConfigDict(from_attributes=True)


class VendorProfileUpdate(BaseModel):
    """Payload for updating vendor profile information."""

    company_name: str
    contact_name: str
    contact_email: EmailStr
    phone_number: str
    remit_to_address: str
    district_key: str | None = None

    def normalized(self) -> "VendorProfileUpdate":
        """Return a copy of the payload with trimmed fields."""

        key_characters = "".join(
            char for char in (self.district_key or "") if char.isalnum()
        ).upper()
        normalized_key = (
            "-".join(
                key_characters[i : i + 4] for i in range(0, len(key_characters), 4)
            )
            if key_characters
            else None
        )

        return VendorProfileUpdate(
            company_name=self.company_name.strip(),
            contact_name=self.contact_name.strip(),
            contact_email=self.contact_email,
            phone_number=self.phone_number.strip(),
            remit_to_address=self.remit_to_address.strip(),
            district_key=normalized_key,
        )
