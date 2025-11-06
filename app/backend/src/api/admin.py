"""Administrative endpoints for managing datasets, users, and vendors."""

import os

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.backend.src.db import get_session_dependency
from app.backend.src.services.seed import seed_development_user

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/seed")
def load_seed_data(session: Session = Depends(get_session_dependency)) -> dict[str, object]:
    """Create (or return) a demo vendor and user for local development."""

    auth0_sub = os.environ.get("AUTH0_DEMO_SUB")
    result = seed_development_user(session, auth0_sub=auth0_sub)
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
        "auth0_sub": result.user.auth0_sub,
    }
