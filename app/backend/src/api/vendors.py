"""Vendor profile endpoints for the vendor portal."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.backend.src.core.security import require_vendor_user
from app.backend.src.db import get_session_dependency
from app.backend.src.models import District, User, Vendor
from app.backend.src.schemas.vendor import (
    VendorDistrictKeySubmission,
    VendorDistrictLink,
    VendorProfile,
    VendorProfileUpdate,
)

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
        is_profile_complete=is_complete,
        district_company_name=vendor.district.company_name if vendor.district else None,
        is_district_linked=is_district_linked,
    )


def _serialize_vendor_district_link(vendor: Vendor) -> VendorDistrictLink:
    """Return the vendor's current district connection."""

    district = vendor.district
    return VendorDistrictLink(
        district_id=district.id if district else None,
        district_name=district.company_name if district else None,
        district_key=district.district_key if district else None,
        is_linked=district is not None,
    )


@router.get("/me", response_model=VendorProfile)
def get_vendor_profile(
    session: Session = Depends(get_session_dependency),
    current_user: User = Depends(require_vendor_user),
) -> VendorProfile:
    """Return the vendor profile for the authenticated user."""

    vendor_id = current_user.vendor_id
    vendor = session.get(Vendor, vendor_id) if vendor_id is not None else None
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

    session.add(vendor)
    session.commit()
    session.refresh(vendor)

    return _serialize_vendor(vendor)


@router.get("/me/district-key", response_model=VendorDistrictLink)
def get_vendor_district_key(
    session: Session = Depends(get_session_dependency),
    current_user: User = Depends(require_vendor_user),
) -> VendorDistrictLink:
    """Return the vendor's currently registered district key, if any."""

    vendor = session.get(Vendor, current_user.vendor_id) if current_user.vendor_id else None
    if vendor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor profile not found",
        )

    return _serialize_vendor_district_link(vendor)


@router.post("/me/district-key", response_model=VendorDistrictLink)
def register_vendor_district_key(
    payload: VendorDistrictKeySubmission,
    session: Session = Depends(get_session_dependency),
    current_user: User = Depends(require_vendor_user),
) -> VendorDistrictLink:
    """Register or update the vendor's district access key."""

    vendor = current_user.vendor
    if vendor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor profile not found",
        )

    normalized_key = payload.normalized()
    if not normalized_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Enter a district access key to continue.",
        )

    district = session.execute(
        select(District).where(District.district_key == normalized_key)
    ).scalar_one_or_none()
    if district is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="We couldn't find a district with that access key.",
        )

    vendor.district = district
    session.add(vendor)
    session.commit()
    session.refresh(vendor)

    return _serialize_vendor_district_link(vendor)
