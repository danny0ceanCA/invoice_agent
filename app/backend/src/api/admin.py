"""Administrative endpoints for managing datasets, users, and vendors."""

import os

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.backend.src.db import get_session_dependency
from app.backend.src.models.user import User
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


# TODO: Remove or disable this bootstrap route after promoting the first admin user.
@router.post("/bootstrap")
def bootstrap_admin(session: Session = Depends(get_session_dependency)) -> dict[str, object]:
    """Promote the first user in the database to an admin role if none exists."""

    existing_admin = session.query(User).filter(User.role == "admin").first()
    if existing_admin:
        return {"message": "Admin already exists"}

    first_user = session.query(User).order_by(User.id).first()
    if first_user is None:
        return {"message": "No users available to promote"}

    first_user.role = "admin"
    session.commit()

    return {
        "message": "First user promoted to admin",
        "email": first_user.email,
    }
