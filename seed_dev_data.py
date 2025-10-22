"""Seed the development database with a demo vendor and user."""

from app.backend.src.db import get_engine, session_scope
from app.backend.src.models.base import Base
from app.backend.src.services.seed import seed_development_user


def main() -> None:
    """Create tables (if needed) and ensure a demo user exists."""

    engine = get_engine()
    Base.metadata.create_all(bind=engine)

    with session_scope() as session:
        result = seed_development_user(session)
        session.flush()

        print("✅ Development data ready!")
        vendor_status = "created" if result.vendor_created else "found"
        user_status = "created" if result.user_created else "found"
        print(
            f"Vendor ({vendor_status}): {result.vendor.name} [id={result.vendor.id}]"
        )
        print(
            f"User ({user_status}): {result.user.name} <{result.user.email}> "
            f"[id={result.user.id}, role={result.user.role}]"
        )
        print()
        print("Use the following header when calling protected APIs:")
        print(f"  X-User-Id: {result.user.id}")


if __name__ == "__main__":
    main()
