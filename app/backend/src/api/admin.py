"""Administrative endpoints for managing datasets, users, and vendors."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.backend.src.db import get_session
from app.backend.src.services.seed import seed_development_user

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/seed")
def load_seed_data(session: Session = Depends(get_session)) -> dict[str, object]:
    """Create (or return) a demo vendor and user for local development."""

    result = seed_development_user(session)
    session.commit()

    return {
        "status": "seeded",
        "vendor_created": result.vendor_created,
        "user_created": result.user_created,
        "vendor": {"id": result.vendor.id, "name": result.vendor.name},
        "user": {
            "id": result.user.id,
            "email": result.user.email,
            "name": result.user.name,
            "role": result.user.role,
        },
        "auth_header": {"X-User-Id": str(result.user.id)},
    }
