"""Unit tests for the administrative user service layer."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[4]))

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_invoice.db")

import pytest
from fastapi import HTTPException

from app.backend.src.db import get_engine, session_scope
from app.backend.src.models import User
from app.backend.src.models.base import Base
from app.backend.src.services import admin_users


@pytest.fixture(autouse=True)
def setup_database() -> None:  # type: ignore[no-untyped-def]
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def seeded_users() -> list[User]:
    with session_scope() as session:
        users = [
            User(email="admin@example.com", name="Admin", role="admin", is_approved=True),
            User(email="vendor@example.com", name="Vendor", role="vendor"),
            User(email="district@example.com", name="District", role="district", is_approved=True),
        ]
        session.add_all(users)
    return users


def test_list_users_returns_all_users(seeded_users: list[User]) -> None:
    with session_scope() as session:
        result = admin_users.list_users(session)

    assert len(result) == 3
    assert result[0].email in {"admin@example.com", "district@example.com", "vendor@example.com"}


def test_list_pending_users_only_includes_unapproved_users(seeded_users: list[User]) -> None:
    with session_scope() as session:
        pending = admin_users.list_pending_users(session)

    assert all(user.is_approved is False for user in pending)
    emails = {user.email for user in pending}
    assert emails == {"vendor@example.com"}


def test_list_pending_users_excludes_inactive_accounts(seeded_users: list[User]) -> None:
    vendor = next(user for user in seeded_users if user.email == "vendor@example.com")

    with session_scope() as session:
        admin_users.decline_user(session, vendor.id)

    with session_scope() as session:
        pending = admin_users.list_pending_users(session)

    assert all(user.email != "vendor@example.com" for user in pending)


def test_approve_user_marks_user_as_approved(seeded_users: list[User]) -> None:
    vendor = next(user for user in seeded_users if user.email == "vendor@example.com")

    with session_scope() as session:
        updated = admin_users.approve_user(session, vendor.id)

    assert updated.is_approved is True
    assert updated.is_active is True


def test_decline_user_marks_user_inactive(seeded_users: list[User]) -> None:
    vendor = next(user for user in seeded_users if user.email == "vendor@example.com")

    with session_scope() as session:
        updated = admin_users.decline_user(session, vendor.id)

    assert updated.is_active is False
    assert updated.is_approved is False


def test_update_user_role_changes_role(seeded_users: list[User]) -> None:
    vendor = next(user for user in seeded_users if user.email == "vendor@example.com")

    with session_scope() as session:
        updated = admin_users.update_user_role(session, vendor.id, "district")

    assert updated.role == "district"


def test_update_user_role_rejects_invalid_value(seeded_users: list[User]) -> None:
    vendor = next(user for user in seeded_users if user.email == "vendor@example.com")

    with session_scope() as session:
        with pytest.raises(HTTPException) as exc_info:
            admin_users.update_user_role(session, vendor.id, "invalid")

    assert exc_info.value.status_code == 400


def test_deactivate_user_marks_account_inactive(seeded_users: list[User]) -> None:
    admin_user = next(user for user in seeded_users if user.email == "admin@example.com")

    with session_scope() as session:
        updated = admin_users.deactivate_user(session, admin_user.id)

    assert updated.is_active is False

