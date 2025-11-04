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
        vendor = Vendor(name="Test Vendor", contact_email="vendor@example.com")
        session.add(vendor)
        session.flush()
        user = User(
            email="user@example.com",
            name="Vendor User",
            role="vendor",
            vendor_id=vendor.id,
        )
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
