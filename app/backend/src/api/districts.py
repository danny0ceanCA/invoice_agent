"""District-facing profile and overview endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.backend.src.core.security import require_district_user
from app.backend.src.db import get_session_dependency
from app.backend.src.models import District, User
from app.backend.src.schemas.district import (
    DistrictProfile,
    DistrictProfileUpdate,
    DistrictVendorOverview,
)
from app.backend.src.services.district_overview import fetch_district_vendor_overview

router = APIRouter(prefix="/districts", tags=["districts"])


def _serialize_district(district: District) -> DistrictProfile:
    """Return a :class:`DistrictProfile` representation for the given district."""

    required_fields = [
        district.company_name,
        district.contact_name,
        district.contact_email,
        district.phone_number,
        district.mailing_address,
    ]
    is_complete = all(
        isinstance(value, str) and value.strip() for value in required_fields
    )

    return DistrictProfile(
        id=district.id,
        company_name=district.company_name,
        contact_name=district.contact_name,
        contact_email=district.contact_email,
        phone_number=district.phone_number,
        mailing_address=district.mailing_address,
        is_profile_complete=is_complete,
    )


@router.get("/me", response_model=DistrictProfile)
def get_district_profile(
    session: Session = Depends(get_session_dependency),
    current_user: User = Depends(require_district_user),
) -> DistrictProfile:
    """Return the district profile for the authenticated user."""

    district_id = current_user.district_id
    if district_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="District profile not found",
        )

    district = session.get(District, district_id)
    if district is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="District profile not found",
        )

    return _serialize_district(district)


@router.put("/me", response_model=DistrictProfile)
def update_district_profile(
    payload: DistrictProfileUpdate,
    session: Session = Depends(get_session_dependency),
    current_user: User = Depends(require_district_user),
) -> DistrictProfile:
    """Update the district profile for the authenticated user."""

    district_id = current_user.district_id
    if district_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="District profile not found",
        )

    district = session.get(District, district_id)
    if district is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="District profile not found",
        )

    normalized = payload.normalized()

    district.company_name = normalized.company_name
    district.contact_name = normalized.contact_name
    district.contact_email = normalized.contact_email
    district.phone_number = normalized.phone_number
    district.mailing_address = normalized.mailing_address

    session.add(district)
    session.commit()
    session.refresh(district)

    return _serialize_district(district)


@router.get("/vendors", response_model=DistrictVendorOverview)
def list_vendor_overview(
    session: Session = Depends(get_session_dependency),
    _: User = Depends(require_district_user),
) -> DistrictVendorOverview:
    """Return vendor performance data for district reviewers."""

    return fetch_district_vendor_overview(session)


__all__ = ["router"]
