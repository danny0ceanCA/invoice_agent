"""Vendor schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .address import PostalAddress, PostalAddressInput


class VendorProfile(BaseModel):
    """Serialized vendor profile details for the portal."""

    id: int
    company_name: str
    contact_name: str | None
    contact_email: EmailStr | None
    phone_number: str | None
    remit_to_address: PostalAddress | None
    is_profile_complete: bool
    district_company_name: str | None
    is_district_linked: bool

    model_config = ConfigDict(from_attributes=True)


class VendorProfileUpdateNormalized(BaseModel):
    """Normalized vendor profile update payload."""

    company_name: str
    contact_name: str
    contact_email: EmailStr
    phone_number: str
    remit_to_address: PostalAddress
    district_key: str | None


class VendorProfileUpdate(BaseModel):
    """Payload for updating vendor profile information."""

    company_name: str
    contact_name: str
    contact_email: EmailStr
    phone_number: str
    remit_to_address: PostalAddressInput
    district_key: str | None = Field(default=None, alias="districtKey")

    model_config = ConfigDict(populate_by_name=True)

    def normalized(self) -> VendorProfileUpdateNormalized:
        """Return a copy of the payload with trimmed fields."""

        normalized_key: str | None = None
        if self.district_key:
            normalized_key = (
                VendorDistrictKeySubmission(district_key=self.district_key)
                .normalized()
                .strip()
            )
            if not normalized_key:
                normalized_key = None

        normalized_address = self.remit_to_address.normalized()

        return VendorProfileUpdateNormalized(
            company_name=self.company_name.strip(),
            contact_name=self.contact_name.strip(),
            contact_email=self.contact_email,
            phone_number=self.phone_number.strip(),
            remit_to_address=normalized_address,
            district_key=normalized_key,
        )


class VendorDistrictKeySubmission(BaseModel):
    """Payload for registering or updating a vendor district key."""

    district_key: str

    def normalized(self) -> str:
        """Return the normalized district key string."""

        key_characters = "".join(char for char in self.district_key if char.isalnum()).upper()
        if not key_characters:
            return ""

        groups = [
            key_characters[i : i + 4]
            for i in range(0, len(key_characters), 4)
        ]
        return "-".join(groups)


class VendorDistrictLink(BaseModel):
    """Representation of the vendor's current district connection."""

    district_id: int | None
    district_name: str | None
    district_key: str | None
    is_linked: bool


__all__ = [
    "VendorProfile",
    "VendorProfileUpdate",
    "VendorProfileUpdateNormalized",
    "VendorDistrictKeySubmission",
    "VendorDistrictLink",
]
