"""API tests for administrative user management endpoints."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[4]))

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_invoice.db")

import pytest
from fastapi.testclient import TestClient

from app.backend.src.api import admin_users as admin_users_api
from app.backend.src.core.security import get_current_user
from app.backend.src.db import get_engine, session_scope
from app.backend.src.main import app
from app.backend.src.models import User
from app.backend.src.models.base import Base


@pytest.fixture(autouse=True)
def setup_database() -> None:  # type: ignore[no-untyped-def]
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def override_admin_dependency() -> None:  # type: ignore[no-untyped-def]
    def _override() -> User:
        with session_scope() as session:
            user = session.query(User).filter(User.role == "admin").first()
            if not user:
                raise RuntimeError("Admin user missing for test")
            return user

    app.dependency_overrides[get_current_user] = _override
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture()
def client(override_admin_dependency) -> TestClient:  # type: ignore[no-untyped-def]
    return TestClient(app)


@pytest.fixture()
def seeded_users() -> dict[str, User]:
    with session_scope() as session:
        admin_user = User(
            email="admin@example.com",
            name="Admin",
            role="admin",
            is_approved=True,
        )
        vendor_user = User(
            email="vendor@example.com",
            name="Vendor",
            role="vendor",
            is_approved=False,
        )
        district_user = User(
            email="district@example.com",
            name="District",
            role="district",
            is_approved=True,
        )
        session.add_all([admin_user, vendor_user, district_user])
    return {
        "admin": admin_user,
        "vendor": vendor_user,
        "district": district_user,
    }


def test_list_users_endpoint_returns_all_users(client: TestClient, seeded_users: dict[str, User]) -> None:
    response = client.get("/api/admin/users")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 3
    assert any(user["email"] == "vendor@example.com" for user in payload)


def test_list_pending_users_endpoint_filters_results(client: TestClient, seeded_users: dict[str, User]) -> None:
    response = client.get("/api/admin/users/pending")
    assert response.status_code == 200
    payload = response.json()
    assert payload == [
        {
            "id": seeded_users["vendor"].id,
            "email": "vendor@example.com",
            "name": "Vendor",
            "role": "vendor",
            "is_approved": False,
            "is_active": True,
            "vendor_id": None,
            "vendor_company_name": None,
            "district_id": None,
            "district_company_name": None,
        }
    ]


def test_approve_user_endpoint_marks_as_approved(client: TestClient, seeded_users: dict[str, User]) -> None:
    vendor_id = seeded_users["vendor"].id
    response = client.patch(f"/api/admin/users/{vendor_id}/approve")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "User approved successfully"
    assert data["user"]["is_approved"] is True
    assert data["user"]["is_active"] is True


def test_decline_user_endpoint_marks_as_inactive(client: TestClient, seeded_users: dict[str, User]) -> None:
    vendor_id = seeded_users["vendor"].id
    response = client.delete(f"/api/admin/users/{vendor_id}/decline")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "User declined successfully"
    assert data["user"]["is_active"] is False
    assert data["user"]["is_approved"] is False


def test_update_user_role_endpoint_changes_role(client: TestClient, seeded_users: dict[str, User]) -> None:
    vendor_id = seeded_users["vendor"].id
    response = client.patch(
        f"/api/admin/users/{vendor_id}/role",
        json={"role": "district"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "district"


def test_update_user_role_endpoint_rejects_invalid_role(
    client: TestClient, seeded_users: dict[str, User]
) -> None:
    vendor_id = seeded_users["vendor"].id
    response = client.patch(
        f"/api/admin/users/{vendor_id}/role",
        json={"role": "invalid"},
    )
    assert response.status_code == 400


def test_deactivate_user_endpoint_marks_inactive(client: TestClient, seeded_users: dict[str, User]) -> None:
    district_id = seeded_users["district"].id
    response = client.patch(f"/api/admin/users/{district_id}/deactivate")
    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_actions_return_not_found_for_missing_user(client: TestClient, seeded_users: dict[str, User]) -> None:
    response = client.patch("/api/admin/users/999/approve")
    assert response.status_code == 404
