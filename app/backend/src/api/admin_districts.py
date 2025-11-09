"""Administrative endpoints for managing districts and their access keys."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.backend.src.core.security import require_admin_user
from ..db import get_session_dependency
from app.backend.src.models import District
from app.backend.src.schemas.district import DistrictProfile, DistrictProfileUpdate

router = APIRouter(prefix="/admin/districts", tags=["admin-districts"])


def _serialize_district(district: District) -> DistrictProfile:
    """Return a :class:`DistrictProfile` representation for administrative views."""

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


@router.get("", response_model=list[DistrictProfile])
def list_districts(
    session: Session = Depends(get_session_dependency),
    _: object = Depends(require_admin_user),
) -> list[DistrictProfile]:
    """Return all districts sorted alphabetically."""

    districts = session.scalars(select(District).order_by(District.company_name.asc())).all()
    return [_serialize_district(district) for district in districts]


class DistrictCreatePayload(DistrictProfileUpdate):
    """Payload for creating a new district from the admin console."""

    district_key: str | None = None

    def normalized(self) -> "DistrictCreatePayload":
        """Return a sanitized payload with trimmed values."""

        normalized_base = super().normalized()
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
        return DistrictCreatePayload(
            company_name=normalized_base.company_name,
            contact_name=normalized_base.contact_name,
            contact_email=normalized_base.contact_email,
            phone_number=normalized_base.phone_number,
            mailing_address=normalized_base.mailing_address,
            district_key=normalized_key,
        )


@router.post("", response_model=DistrictProfile, status_code=status.HTTP_201_CREATED)
def create_district(
    payload: DistrictCreatePayload,
    session: Session = Depends(get_session_dependency),
    _: object = Depends(require_admin_user),
) -> DistrictProfile:
    """Create a new district and optionally assign a specific access key."""

    normalized = payload.normalized()

    if normalized.district_key:
        duplicate = (
            session.query(District)
            .filter(District.district_key == normalized.district_key)
            .one_or_none()
        )
        if duplicate is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Another district already uses that access key.",
            )

    district = District(
        company_name=normalized.company_name,
        contact_name=normalized.contact_name or None,
        contact_email=normalized.contact_email or None,
        phone_number=normalized.phone_number or None,
        mailing_address=normalized.mailing_address or None,
    )
    if normalized.district_key:
        district.district_key = normalized.district_key

    session.add(district)
    session.commit()
    session.refresh(district)

    return _serialize_district(district)


__all__ = ["router"]
