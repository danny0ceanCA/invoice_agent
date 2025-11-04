"""Integration-flavored smoke tests for the FastAPI app."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pandas as pd
import pytest
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[4]))

# Configure environment before application imports
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_invoice.db")
os.environ.setdefault("AWS_S3_BUCKET", "local")
os.environ.setdefault("LOCAL_STORAGE_PATH", "/tmp/invoice-agent-tests")

from app.backend.src.agents.invoice_agent import InvoiceAgent
from app.backend.src.db import get_engine, session_scope
from app.backend.src.main import app
from app.backend.src.models import Invoice, InvoiceLineItem, Vendor, User
from app.backend.src.models.base import Base


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
            .filter(Vendor.name == "Test Vendor")
            .one_or_none()
        )
        if vendor is None:
            vendor = Vendor(name="Test Vendor", contact_email="vendor@example.com")
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
                vendor_id=vendor.id,
            )
            session.add(user)
            session.flush()
        elif user.vendor_id != vendor.id:
            user.vendor_id = vendor.id
            session.add(user)

        vendor_id = vendor.id
        user_id = user.id
    return vendor_id, user_id


@pytest.fixture()
def admin_user() -> int:
    with session_scope() as session:
        admin = (
            session.query(User)
            .filter(User.email == "admin@example.com")
            .one_or_none()
        )
        if admin is None:
            admin = User(
                email="admin@example.com",
                name="District Admin",
                role="admin",
            )
            session.add(admin)
            session.flush()
        return admin.id


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


def _create_invoice(
    vendor_id: int,
    student: str,
    service_month: str,
    invoice_date: datetime,
) -> str:
    invoice_number = f"{student.replace(' ', '-')}-{uuid4().hex[:8]}"
    pdf_key = f"invoices/{uuid4().hex}.pdf"
    with session_scope() as session:
        invoice = Invoice(
            vendor_id=vendor_id,
            student_name=student,
            invoice_number=invoice_number,
            invoice_code=f"AUTO-{service_month.replace(' ', '-')}",
            service_month=service_month,
            invoice_date=invoice_date,
            total_hours=7.5,
            total_cost=525.0,
            status="generated",
            pdf_s3_key=pdf_key,
        )
        session.add(invoice)
        session.flush()
        line_item = InvoiceLineItem(
            invoice_id=invoice.id,
            student=student,
            clinician="Sample Clinician",
            service_code="RN-SCUSD",
            hours=7.5,
            rate=70.0,
            cost=525.0,
            service_date=invoice_date.strftime("%Y-%m-%d"),
        )
        session.add(line_item)
    return invoice_number


def test_vendor_dashboard_invoices_endpoint(
    client: TestClient, vendor_and_user: tuple[int, int]
) -> None:
    vendor_id, user_id = vendor_and_user
    invoice_number = _create_invoice(
        vendor_id,
        student="Student B",
        service_month="May 2024",
        invoice_date=datetime(2024, 5, 31, tzinfo=timezone.utc),
    )

    response = client.get(
        "/api/vendors/me/invoices",
        headers={"X-User-Id": str(user_id)},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["vendor"]["id"] == vendor_id
    assert payload["summary"]["invoice_count"] >= 1
    assert any(
        invoice["invoice_number"] == invoice_number for invoice in payload["invoices"]
    )


def test_district_vendor_overview_requires_admin(
    client: TestClient, vendor_and_user: tuple[int, int], admin_user: int
) -> None:
    vendor_id, vendor_user_id = vendor_and_user
    _create_invoice(
        vendor_id,
        student="Student District",
        service_month="April 2024",
        invoice_date=datetime(2024, 4, 30, tzinfo=timezone.utc),
    )

    forbidden = client.get(
        "/api/district/vendors",
        headers={"X-User-Id": str(vendor_user_id)},
    )
    assert forbidden.status_code == 403

    allowed = client.get(
        "/api/district/vendors",
        headers={"X-User-Id": str(admin_user)},
    )
    assert allowed.status_code == 200
    payload = allowed.json()
    assert payload["totals"]["vendors"] >= 1
    assert any(vendor["id"] == vendor_id for vendor in payload["vendors"])


def test_generate_invoices_inline_fallback(
    client: TestClient,
    vendor_and_user: tuple[int, int],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    vendor_id, user_id = vendor_and_user

    from app.backend.src.api import invoices as invoices_module

    def _raise(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("broker unavailable")

    monkeypatch.setattr(invoices_module.process_invoice, "apply_async", _raise)

    dataframe = pd.DataFrame(
        {
            "Client": ["Inline Student"],
            "Schedule Date": ["2024-02-02"],
            "Hours": [2.0],
            "Employee": ["Nurse 99"],
            "Service Code": ["RN-SCUSD"],
        }
    )
    upload_path = tmp_path / "inline.xlsx"
    dataframe.to_excel(upload_path, index=False)

    with upload_path.open("rb") as handle:
        response = client.post(
            "/api/invoices/generate",
            data={
                "vendor_id": str(vendor_id),
                "invoice_date": "2024-02-28",
                "service_month": "February 2024",
            },
            files={
                "file": (
                    "inline.xlsx",
                    handle,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
            headers={"X-User-Id": str(user_id)},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["queue"] == "inline"
    assert payload["status"] in {"completed", "skipped"}
    assert payload["job_id"].startswith("inline-")

    with session_scope() as session:
        invoices = session.query(Invoice).filter(Invoice.student_name == "Inline Student").all()
        assert len(invoices) == 1
