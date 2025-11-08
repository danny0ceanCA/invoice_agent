"""Authentication and authorization helpers."""

from fastapi import APIRouter, Depends

from app.backend.src.core.security import get_current_user
from app.backend.src.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me")
def read_current_user(current_user: User = Depends(get_current_user)) -> dict[str, object | None]:
    """Return the authenticated user's profile."""

    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "role": current_user.role,
        "vendor_id": current_user.vendor_id,
        "district_id": getattr(current_user, "district_id", None),
        "auth0_sub": current_user.auth0_sub,
        "needs_role_selection": current_user.role is None,
    }
