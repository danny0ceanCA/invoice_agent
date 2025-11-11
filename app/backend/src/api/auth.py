"""Authentication and authorization helpers."""

from datetime import datetime

from fastapi import APIRouter, Depends

from app.backend.src.core.security import get_current_user
from app.backend.src.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me")
def read_current_user(current_user: User = Depends(get_current_user)) -> dict[str, object | None]:
    """Return the authenticated user's profile."""

    active_district_id = current_user.active_district_id
    memberships = []
    ordered_memberships = sorted(
        current_user.district_memberships,
        key=lambda entry: entry.created_at or datetime.min,
    )
    for membership in ordered_memberships:
        memberships.append(
            {
                "district_id": membership.district_id,
                "company_name": membership.district.company_name,
                "district_key": membership.district.district_key,
                "is_active": membership.district_id == active_district_id,
            }
        )

    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "role": current_user.role,
        "vendor_id": current_user.vendor_id,
        "district_id": active_district_id,
        "active_district_id": active_district_id,
        "district_memberships": memberships,
        "auth0_sub": current_user.auth0_sub,
        "needs_role_selection": current_user.role is None,
    }
