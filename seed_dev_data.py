"""Seed the development database with a demo vendor and user."""

import os

from app.backend.src.db import get_engine, session_scope
from app.backend.src.models.base import Base
from app.backend.src.services.seed import seed_development_user


def main() -> None:
    """Create tables (if needed) and ensure a demo user exists."""

    engine = get_engine()
    Base.metadata.create_all(bind=engine)

    with session_scope() as session:
        auth0_sub = os.environ.get("AUTH0_DEMO_SUB")
        result = seed_development_user(session, auth0_sub=auth0_sub)
        session.flush()

        print("✅ Development data ready!")
        if result.vendor_created:
            vendor_status = "created"
        elif result.vendor_updated:
            vendor_status = "updated"
        else:
            vendor_status = "unchanged"

        if result.user_created:
            user_status = "created"
        elif result.user_updated:
            user_status = "updated"
        else:
            user_status = "unchanged"
        print(
            f"Vendor ({vendor_status}): {result.vendor.company_name} [id={result.vendor.id}]"
        )
        print(
            f"User ({user_status}): {result.user.name} <{result.user.email}> "
            f"[id={result.user.id}, role={result.user.role}]"
        )
        print()
        if auth0_sub:
            print(f"Linked Auth0 subject: {auth0_sub}")
        else:
            print("Set AUTH0_DEMO_SUB to automatically link an Auth0 subject during seeding.")


if __name__ == "__main__":
    main()
