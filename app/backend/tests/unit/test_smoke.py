"""Integration-flavored smoke tests for the FastAPI app."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[4]))

from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

# Configure environment before application imports
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_invoice.db")
os.environ.setdefault("AWS_S3_BUCKET", "local")
os.environ.setdefault("LOCAL_STORAGE_PATH", "/tmp/invoice-agent-tests")

from app.backend.src.agents.invoice_agent import InvoiceAgent
from app.backend.src.db import get_engine, session_scope
from app.backend.src.main import app
from app.backend.src.models import Invoice, Vendor, User
from app.backend.src.models.base import Base
from app.backend.src.core.security import get_current_user


@pytest.fixture(scope="module", autouse=True)
def setup_database() -> None:
    engine = get_engine()
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture()
def vendor_and_user() -> tuple[int, int]:
    with session_scope() as session:
        vendor = (
            session.query(Vendor)
            .filter(Vendor.company_name == "Test Vendor")
            .one_or_none()
        )
        if vendor is None:
            vendor = Vendor(
                company_name="Test Vendor",
                contact_email="vendor@example.com",
                contact_name="Vendor Owner",
                phone_number="555-555-5555",
                remit_to_address="123 Main St\nSacramento, CA 95814",
            )
            session.add(vendor)
            session.flush()

        user = (
            session.query(User)
            .filter(User.email == "user@example.com")
            .one_or_none()
        )
        if user is None:
            user = User(
                email="user@example.com",
                name="Vendor User",
                role="vendor",
                is_approved=True,
                vendor_id=vendor.id,
            )
            session.add(user)
            session.flush()
        else:
            if user.vendor_id != vendor.id:
                user.vendor_id = vendor.id
            if not user.is_approved:
                user.is_approved = True
            session.add(user)
            session.flush()

        vendor_id = vendor.id
        user_id = user.id
    return vendor_id, user_id


def test_liveness_endpoint(client: TestClient) -> None:
    response = client.get("/api/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "live"


def test_invoice_agent_generates_invoices(tmp_path: Path, vendor_and_user: tuple[int, int]) -> None:
    vendor_id, _ = vendor_and_user
    data = pd.DataFrame(
        {
            "Client": ["Student A", "Student A"],
            "Schedule Date": ["2024-01-03", "2024-01-04"],
            "Hours": [2.5, 3.0],
            "Employee": ["Nurse 1", "Nurse 1"],
            "Service Code": ["HHA-SCUSD", "HHA-SCUSD"],
        }
    )
    file_path = tmp_path / "timesheet.xlsx"
    data.to_excel(file_path, index=False)

    agent = InvoiceAgent(
        vendor_id=vendor_id,
        invoice_date=datetime(2024, 1, 31),
        service_month="January 2024",
        invoice_code="INV-001",
    )

    result = agent.run(file_path)
    assert "invoice_ids" in result
    assert len(result["invoice_ids"]) == 1

    with session_scope() as session:
        invoices = session.query(Invoice).all()
        assert len(invoices) == 1
        assert invoices[0].total_hours == pytest.approx(5.5)
        assert invoices[0].status == "generated"


def test_vendor_profile_endpoints(
    client: TestClient, vendor_and_user: tuple[int, int]
) -> None:
    vendor_id, user_id = vendor_and_user

    def override_current_user() -> User:
        with session_scope() as session:
            user = session.get(User, user_id)
            assert user is not None
            # Ensure the vendor relationship is loaded before detaching
            _ = user.vendor
            return user

    app.dependency_overrides[get_current_user] = override_current_user

    payload = {
        "company_name": "Responsive Healthcare Associates",
        "contact_name": "Regina Martinez",
        "contact_email": "regina@responsivehc.com",
        "phone_number": "916-555-0102",
        "remit_to_address": "Responsive Healthcare Associates\nPO Box 1234\nSacramento, CA 95824",
    }

    try:
        response = client.get("/api/vendors/me")
        assert response.status_code == 200
        data = response.json()
        assert data["company_name"] == "Test Vendor"

        response = client.put("/api/vendors/me", json=payload)
        assert response.status_code == 200
        updated = response.json()
        assert updated["company_name"] == payload["company_name"]
        assert updated["contact_name"] == payload["contact_name"]
        assert updated["is_profile_complete"] is True
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    with session_scope() as session:
        vendor = session.get(Vendor, vendor_id)
        assert vendor is not None
        assert vendor.company_name == payload["company_name"]
        assert vendor.contact_name == payload["contact_name"]
