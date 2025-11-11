from __future__ import annotations

import sys
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
import importlib.metadata
import types
from zipfile import ZipFile

import pytest
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

sys.path.append(str(Path(__file__).resolve().parents[4]))

if "jose" not in sys.modules:
    jose_module = types.ModuleType("jose")
    jose_module.JWTError = Exception
    jose_module.jwt = types.SimpleNamespace(
        get_unverified_header=lambda token: {"kid": "test"},
        decode=lambda *args, **kwargs: {
            "sub": "test-user",
            "aud": ["test"],
        },
    )
    sys.modules["jose"] = jose_module
    sys.modules["jose.jwt"] = jose_module.jwt

if "email_validator" not in sys.modules:
    email_validator_module = types.ModuleType("email_validator")

    class EmailNotValidError(Exception):
        """Fallback error used when email_validator isn't installed."""

    def validate_email(address: str, *args: object, **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(email=address)

    email_validator_module.EmailNotValidError = EmailNotValidError
    email_validator_module.validate_email = validate_email
    sys.modules["email_validator"] = email_validator_module

if not hasattr(importlib.metadata, "_invoice_agent_email_validator_patch"):
    original_version = importlib.metadata.version
    original_distribution = importlib.metadata.distribution

    def patched_version(name: str) -> str:
        if name == "email-validator":
            return "2.0.0"
        return original_version(name)

    def patched_distribution(name: str):
        if name == "email-validator":
            class _DummyDistribution:
                version = "2.0.0"

            return _DummyDistribution()
        return original_distribution(name)

    importlib.metadata.version = patched_version  # type: ignore[assignment]
    importlib.metadata.distribution = patched_distribution  # type: ignore[assignment]
    importlib.metadata._invoice_agent_email_validator_patch = True

from app.backend.src.main import app
from app.backend.src.core.security import require_district_user
from app.backend.src.db import Base, get_engine, session_scope
from app.backend.src.models import Invoice
from app.backend.src.models.vendor import Vendor


@pytest.fixture(autouse=True)
def override_district_user():
    app.dependency_overrides[require_district_user] = (
        lambda: SimpleNamespace(email="district@example.com")
    )
    yield
    app.dependency_overrides.pop(require_district_user, None)


@pytest.fixture(autouse=True)
def ensure_vendor_record():
    Base.metadata.create_all(bind=get_engine())
    with session_scope() as session:
        vendor = session.get(Vendor, 42)
        if vendor is None:
            vendor = Vendor(
                id=42,
                company_name="Always Home Nursing",
                contact_email="contact@alwayshome.com",
            )
            session.add(vendor)
        else:
            vendor.company_name = "Always Home Nursing"
            if not vendor.contact_email:
                vendor.contact_email = "contact@alwayshome.com"
            session.add(vendor)
    yield


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@patch("app.backend.src.api.invoices.get_s3_client")
def test_download_zip_returns_existing_archive(
    mock_get_client: MagicMock,
    client: TestClient,
) -> None:
    mock_client = MagicMock()
    mock_client.head_object.return_value = {"ContentLength": 1024}
    mock_client.generate_presigned_url.return_value = "https://example.com/archive.zip"
    mock_get_client.return_value = mock_client

    response = client.get("/api/invoices/download-zip/42/2024-01")

    assert response.status_code == 200
    assert response.json() == {"download_url": "https://example.com/archive.zip"}
    mock_client.get_paginator.assert_not_called()
    mock_client.upload_fileobj.assert_not_called()
    mock_client.generate_presigned_url.assert_called_once_with(
        "get_object",
        Params={
            "Bucket": "invoice-agent-files",
            "Key": "invoices/AlwaysHomeNursing/2024/01/AlwaysHomeNursing_2024_01_invoices.zip",
            "ResponseContentDisposition": 'attachment; filename="AlwaysHomeNursing_2024_01_invoices.zip"',
            "ResponseContentType": "application/zip",
        },
        ExpiresIn=3600,
    )


@patch("app.backend.src.api.invoices.get_s3_client")
def test_download_zip_creates_archive(
    mock_get_client: MagicMock,
    client: TestClient,
) -> None:
    mock_client = MagicMock()
    mock_client.head_object.side_effect = ClientError(
        {"Error": {"Code": "404", "Message": "Not Found"}},
        "HeadObject",
    )

    paginator = MagicMock()
    paginator.paginate.return_value = [
        {
            "Contents": [
                {
                    "Key": "invoices/AlwaysHomeNursing/2024/01/student-a.pdf",
                    "LastModified": datetime(2024, 1, 5, 10, 15, tzinfo=timezone.utc),
                    "Size": 4096,
                }
            ]
        }
    ]
    mock_client.get_paginator.return_value = paginator

    uploaded: dict[str, object] = {}

    def fake_download_fileobj(*, Bucket: str, Key: str, Fileobj: BytesIO) -> None:
        Fileobj.write(b"%PDF-test")

    def fake_upload_fileobj(
        Fileobj: BytesIO, *, Bucket: str, Key: str, ExtraArgs: dict | None = None
    ) -> None:
        uploaded["bucket"] = Bucket
        uploaded["key"] = Key
        uploaded["extra_args"] = ExtraArgs or {}
        uploaded["payload"] = Fileobj.read()

    mock_client.download_fileobj.side_effect = fake_download_fileobj
    mock_client.upload_fileobj.side_effect = fake_upload_fileobj
    mock_get_client.return_value = mock_client

    mock_client.generate_presigned_url.return_value = (
        "https://example.com/new-archive.zip"
    )

    response = client.get("/api/invoices/download-zip/42/2024-01")

    assert response.status_code == 200
    assert response.json() == {"download_url": "https://example.com/new-archive.zip"}

    assert uploaded["bucket"] == "invoice-agent-files"
    assert (
        uploaded["key"]
        == "invoices/AlwaysHomeNursing/2024/01/AlwaysHomeNursing_2024_01_invoices.zip"
    )
    assert uploaded["extra_args"] == {"ContentType": "application/zip"}
    assert mock_client.download_fileobj.call_count == 1
    assert mock_client.upload_fileobj.call_count == 1

    archive = ZipFile(BytesIO(uploaded["payload"]))
    assert sorted(archive.namelist()) == ["invoice_summary.csv", "student-a.pdf"]

    summary = archive.read("invoice_summary.csv").decode("utf-8")
    assert "Invoice Name,S3 Key,Last Modified,Size (KB)" in summary
    assert "student-a.pdf" in summary
    assert "invoices/AlwaysHomeNursing/2024/01/student-a.pdf" in summary
    assert "2024-01-05T10:15:00Z" in summary
    assert "4.00" in summary

    pdf_content = archive.read("student-a.pdf")
    assert pdf_content == b"%PDF-test"

    mock_client.generate_presigned_url.assert_called_with(
        "get_object",
        Params={
            "Bucket": "invoice-agent-files",
            "Key": "invoices/AlwaysHomeNursing/2024/01/AlwaysHomeNursing_2024_01_invoices.zip",
            "ResponseContentDisposition": 'attachment; filename="AlwaysHomeNursing_2024_01_invoices.zip"',
            "ResponseContentType": "application/zip",
        },
        ExpiresIn=3600,
    )


def test_list_vendor_invoices_returns_monthly_records(client: TestClient) -> None:
    with session_scope() as session:
        session.query(Invoice).delete()
        invoice = Invoice(
            vendor_id=42,
            upload_id=None,
            student_name="Lola Day",
            invoice_number="INV-2025-11-001",
            invoice_code="CODE-001",
            service_month="November 2025",
            invoice_date=datetime(2025, 11, 11, 8, 52, 31, tzinfo=timezone.utc),
            total_hours=5.0,
            total_cost=1800.0,
            status="approved",
            pdf_s3_key="invoices/ActionSupportiveCare/2025/11/Invoice_Lola_Day_November_2025.pdf",
        )
        session.add(invoice)
        session.commit()
        invoice_id = invoice.id

    response = client.get("/api/invoices/42/2025/11")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert len(payload) == 1
    entry = payload[0]

    assert entry["invoice_id"] == invoice_id
    assert entry["vendor_id"] == 42
    assert entry["company"] == "Always Home Nursing"
    assert entry["invoice_name"] == "Invoice_Lola_Day_November_2025.pdf"
    assert (
        entry["s3_key"]
        == "invoices/ActionSupportiveCare/2025/11/Invoice_Lola_Day_November_2025.pdf"
    )
    assert entry["amount"] == pytest.approx(1800.0)
    assert entry["status"] == "approved"
    assert entry["uploaded_at"] == "2025-11-11T08:52:31Z"

    with session_scope() as session:
        session.query(Invoice).delete()


def test_list_vendor_invoices_handles_missing_month(client: TestClient) -> None:
    with session_scope() as session:
        session.query(Invoice).delete()

    response = client.get("/api/invoices/42/2025/12")

    assert response.status_code == 200
    assert response.json() == []


def test_list_vendor_invoices_unknown_vendor(client: TestClient) -> None:
    response = client.get("/api/invoices/999/2025/11")

    assert response.status_code == 404
