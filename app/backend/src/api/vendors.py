"""Vendor profile endpoints for the vendor portal."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.backend.src.core.security import require_vendor_user
from app.backend.src.db import get_session_dependency
from app.backend.src.models import District, User, Vendor
from app.backend.src.schemas.vendor import VendorProfile, VendorProfileUpdate

router = APIRouter(prefix="/vendors", tags=["vendors"])


def _serialize_vendor(vendor: Vendor) -> VendorProfile:
    """Return a :class:`VendorProfile` representation for the given vendor."""

    required_fields = [
        vendor.company_name,
        vendor.contact_name,
        vendor.contact_email,
        vendor.phone_number,
        vendor.remit_to_address,
    ]
    is_complete = all(
        isinstance(value, str) and value.strip() for value in required_fields
    )
    is_district_linked = vendor.district is not None

    return VendorProfile(
        id=vendor.id,
        company_name=vendor.company_name,
        contact_name=vendor.contact_name,
        contact_email=vendor.contact_email,
        phone_number=vendor.phone_number,
        remit_to_address=vendor.remit_to_address,
        is_profile_complete=is_complete and is_district_linked,
        district_company_name=vendor.district.company_name if vendor.district else None,
        is_district_linked=is_district_linked,
    )


@router.get("/me", response_model=VendorProfile)
def get_vendor_profile(
    current_user: User = Depends(require_vendor_user),
) -> VendorProfile:
    """Return the vendor profile for the authenticated user."""

    vendor = current_user.vendor
    if vendor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor profile not found",
        )
    return _serialize_vendor(vendor)


@router.put("/me", response_model=VendorProfile)
def update_vendor_profile(
    payload: VendorProfileUpdate,
    session: Session = Depends(get_session_dependency),
    current_user: User = Depends(require_vendor_user),
) -> VendorProfile:
    """Update the vendor profile for the authenticated user."""

    vendor = current_user.vendor
    if vendor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor profile not found",
        )

    normalized = payload.normalized()

    vendor.company_name = normalized.company_name
    vendor.contact_name = normalized.contact_name
    vendor.contact_email = normalized.contact_email
    vendor.phone_number = normalized.phone_number
    vendor.remit_to_address = normalized.remit_to_address

    if normalized.district_key:
        district = session.execute(
            select(District).where(District.district_key == normalized.district_key)
        ).scalar_one_or_none()
        if district is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="We couldn't find a district with that access key.",
            )
        vendor.district = district
    elif vendor.district_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A district access key is required to link your organization.",
        )

    session.add(vendor)
    session.commit()
    session.refresh(vendor)

    return _serialize_vendor(vendor)
