"""District-facing profile and overview endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload

from app.backend.src.core.security import require_district_user
from ..db import get_session_dependency
from app.backend.src.models import District, DistrictMembership, User
from app.backend.src.schemas.district import (
    DistrictKeySubmission,
    DistrictMembershipCollection,
    DistrictMembershipEntry,
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
        district.district_key,
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
        district_key=district.district_key,
        is_profile_complete=is_complete,
    )


def _get_active_membership(
    session: Session, current_user: User
) -> DistrictMembership | None:
    """Return the active membership for the current user, if any."""

    db_user = session.get(User, current_user.id)
    if db_user is None:
        return None

    active_id = db_user.active_district_id
    membership: DistrictMembership | None = None

    if active_id is not None:
        membership = (
            session.query(DistrictMembership)
            .options(selectinload(DistrictMembership.district))
            .filter(
                DistrictMembership.user_id == db_user.id,
                DistrictMembership.district_id == active_id,
            )
            .one_or_none()
        )

    if membership is None:
        membership = (
            session.query(DistrictMembership)
            .options(selectinload(DistrictMembership.district))
            .filter(DistrictMembership.user_id == db_user.id)
            .order_by(DistrictMembership.created_at.asc())
            .first()
        )
        if membership is not None and getattr(db_user, "district_id", None) != membership.district_id:
            db_user.district_id = membership.district_id
            session.add(db_user)
            session.commit()
            session.refresh(db_user)
            current_user.district_id = db_user.district_id

    return membership


def _serialize_memberships(
    memberships: list[DistrictMembership], active_id: int | None
) -> DistrictMembershipCollection:
    """Return a membership collection payload."""

    entries = [
        DistrictMembershipEntry(
            district_id=membership.district_id,
            company_name=membership.district.company_name,
            district_key=membership.district.district_key,
            is_active=membership.district_id == active_id,
        )
        for membership in memberships
    ]

    return DistrictMembershipCollection(
        active_district_id=active_id,
        memberships=entries,
    )


@router.get("/me", response_model=DistrictProfile)
def get_district_profile(
    session: Session = Depends(get_session_dependency),
    current_user: User = Depends(require_district_user),
) -> DistrictProfile:
    """Return the district profile for the authenticated user."""

    membership = _get_active_membership(session, current_user)
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="District profile not found",
        )

    district = membership.district
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

    membership = _get_active_membership(session, current_user)
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="District profile not found",
        )

    district = membership.district
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
    current_user: User = Depends(require_district_user),
) -> DistrictVendorOverview:
    """Return vendor performance data for district reviewers."""

    membership = _get_active_membership(session, current_user)
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="District profile not found",
        )

    return fetch_district_vendor_overview(session, membership.district_id)


@router.get("/memberships", response_model=DistrictMembershipCollection)
def list_memberships(
    session: Session = Depends(get_session_dependency),
    current_user: User = Depends(require_district_user),
) -> DistrictMembershipCollection:
    """Return all district memberships for the authenticated user."""

    memberships = (
        session.query(DistrictMembership)
        .options(selectinload(DistrictMembership.district))
        .filter(DistrictMembership.user_id == current_user.id)
        .order_by(DistrictMembership.created_at.asc())
        .all()
    )
    active_id = current_user.active_district_id

    return _serialize_memberships(memberships, active_id)


@router.post("/memberships", response_model=DistrictMembershipCollection)
def add_membership(
    payload: DistrictKeySubmission,
    session: Session = Depends(get_session_dependency),
    current_user: User = Depends(require_district_user),
) -> DistrictMembershipCollection:
    """Link the authenticated user to a district using an access key."""

    normalized = payload.normalized()
    if not normalized.district_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A district access key is required.",
        )

    district = (
        session.query(District)
        .filter(District.district_key == normalized.district_key)
        .one_or_none()
    )
    if district is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="We couldn't find a district with that access key.",
        )

    existing = (
        session.query(DistrictMembership)
        .filter(
            DistrictMembership.user_id == current_user.id,
            DistrictMembership.district_id == district.id,
        )
        .one_or_none()
    )
    db_user = session.get(User, current_user.id)
    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User account not found.",
        )
    if existing is None:
        membership = DistrictMembership(
            user_id=current_user.id,
            district_id=district.id,
        )
        session.add(membership)
        if getattr(db_user, "district_id", None) is None:
            db_user.district_id = district.id
            session.add(db_user)
        session.commit()
    else:
        membership = existing
        if getattr(db_user, "district_id", None) is None:
            db_user.district_id = membership.district_id
            session.add(db_user)
            session.commit()

    session.refresh(db_user)
    current_user.district_id = db_user.district_id

    memberships = (
        session.query(DistrictMembership)
        .options(selectinload(DistrictMembership.district))
        .filter(DistrictMembership.user_id == current_user.id)
        .order_by(DistrictMembership.created_at.asc())
        .all()
    )
    active_id = db_user.active_district_id

    return _serialize_memberships(memberships, active_id)


@router.post("/memberships/{district_id}/activate", response_model=DistrictMembershipCollection)
def activate_membership(
    district_id: int,
    session: Session = Depends(get_session_dependency),
    current_user: User = Depends(require_district_user),
) -> DistrictMembershipCollection:
    """Set the active district for the authenticated user."""

    membership = (
        session.query(DistrictMembership)
        .filter(
            DistrictMembership.user_id == current_user.id,
            DistrictMembership.district_id == district_id,
        )
        .one_or_none()
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="District membership not found.",
        )

    db_user = session.get(User, current_user.id)
    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User account not found.",
        )

    if getattr(db_user, "district_id", None) != district_id:
        db_user.district_id = district_id
        session.add(db_user)
        session.commit()
        session.refresh(db_user)
        current_user.district_id = db_user.district_id

    memberships = (
        session.query(DistrictMembership)
        .options(selectinload(DistrictMembership.district))
        .filter(DistrictMembership.user_id == current_user.id)
        .order_by(DistrictMembership.created_at.asc())
        .all()
    )

    return _serialize_memberships(memberships, db_user.active_district_id)


__all__ = ["router"]
