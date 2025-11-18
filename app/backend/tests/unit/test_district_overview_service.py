import os
import sys
from datetime import datetime, timezone
from pathlib import Path
import types
import importlib.metadata as importlib_metadata

sys.path.append(str(Path(__file__).resolve().parents[4]))

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_invoice.db")

email_validator_stub = types.ModuleType("email_validator")


class EmailNotValidError(ValueError):
    """Fallback error used when email_validator isn't installed."""


def validate_email(address: str, **_: object) -> types.SimpleNamespace:
    local_part = address.split("@", 1)[0]
    return types.SimpleNamespace(
        email=address,
        normalized=address,
        local_part=local_part,
    )


email_validator_stub.EmailNotValidError = EmailNotValidError
email_validator_stub.validate_email = validate_email
email_validator_stub.caching_resolver = None
sys.modules.setdefault("email_validator", email_validator_stub)


class _FakeDistribution:
    version = "2.0.0"


_original_distribution = importlib_metadata.distribution


def _fake_distribution(name: str) -> importlib_metadata.Distribution:  # type: ignore[type-arg]
    if name == "email-validator":
        return _FakeDistribution()  # type: ignore[return-value]
    return _original_distribution(name)


importlib_metadata.distribution = _fake_distribution  # type: ignore[assignment]

import pytest

from app.backend.src.db import get_engine, session_scope
from app.backend.src.models import District, Invoice, InvoiceLineItem, Vendor
from app.backend.src.db.base import Base
from app.backend.src.services.district_overview import fetch_district_vendor_overview


@pytest.fixture(autouse=True)
def setup_database() -> None:  # type: ignore[no-untyped-def]
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_fetch_overview_includes_invoice_pdf_url(monkeypatch: pytest.MonkeyPatch) -> None:
    generated_urls: list[str] = []

    def fake_generate_presigned_url(
        key: str,
        *,
        expires_in: int = 3600,
        download_name: str | None = None,
        response_content_type: str | None = None,
    ) -> str:
        assert response_content_type == "application/pdf"
        url = f"https://example.com/{key}?expires={expires_in}"
        if download_name:
            url += f"&filename={download_name}"
        generated_urls.append(url)
        return url

    monkeypatch.setattr(
        "app.backend.src.services.district_overview.generate_presigned_url",
        fake_generate_presigned_url,
    )

    with session_scope() as session:
        district = District(company_name="Central District", district_key="ABC123")
        vendor = Vendor(
            company_name="Therapy Group",
            contact_email="contact@therapy.com",
            district_key="ABC123",
        )
        session.add_all([district, vendor])
        session.flush()

        invoice = Invoice(
            vendor_id=vendor.id,
            upload_id=None,
            student_name="Student One",
            invoice_number="INV-001",
            invoice_code="CODE-001",
            service_month="January 2024",
            invoice_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            total_hours=1.0,
            total_cost=150.0,
            status="approved",
            pdf_s3_key="invoices/INV-001.pdf",
        )
        session.add(invoice)
        session.flush()

        session.add(
            InvoiceLineItem(
                invoice_id=invoice.id,
                student="Student One",
                clinician="Clinician A",
                service_code="OT",
                hours=1.0,
                rate=150.0,
                cost=150.0,
                service_date="2024-01-10",
            )
        )

    with session_scope() as session:
        overview = fetch_district_vendor_overview(session, district.id)

    assert overview.vendors, "Expected at least one vendor in the overview"
    vendor_profile = overview.vendors[0]

    assert vendor_profile.invoices, "Vendor invoices should not be empty"
    assert generated_urls, "Presigned URL generator was not called"

    first_year = next(iter(vendor_profile.invoices))
    first_invoice = vendor_profile.invoices[first_year][0]

    assert first_invoice.download_url == generated_urls[0]
    assert (
        first_invoice.download_url
        == "https://example.com/invoices/INV-001.pdf?expires=3600&filename=INV-001.pdf"
    )
    assert first_invoice.pdf_url == first_invoice.download_url
    assert first_invoice.pdf_s3_key == "invoices/INV-001.pdf"
    assert first_invoice.students[0].pdf_s3_key == "invoices/INV-001.pdf"


def test_fetch_overview_uses_service_month_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    generated_urls: list[str] = []

    def fake_generate_presigned_url(
        key: str,
        *,
        expires_in: int = 3600,
        download_name: str | None = None,
        response_content_type: str | None = None,
    ) -> str:
        assert response_content_type == "application/pdf"
        url = f"https://example.com/{key}?expires={expires_in}"
        if download_name:
            url += f"&filename={download_name}"
        generated_urls.append(url)
        return url

    monkeypatch.setattr(
        "app.backend.src.services.district_overview.generate_presigned_url",
        fake_generate_presigned_url,
    )

    with session_scope() as session:
        district = District(company_name="Central District", district_key="ABC123")
        vendor = Vendor(
            company_name="Therapy Group",
            contact_email="contact@therapy.com",
            district_key="ABC123",
        )
        session.add_all([district, vendor])
        session.flush()

        invoice = Invoice(
            vendor_id=vendor.id,
            upload_id=None,
            student_name="Student Two",
            invoice_number="INV-002",
            invoice_code="CODE-002",
            service_month="October_2025",
            service_month_num=None,
            invoice_date=datetime(2025, 11, 15, tzinfo=timezone.utc),
            total_hours=1.0,
            total_cost=200.0,
            status="approved",
            pdf_s3_key="invoices/INV-002.pdf",
        )
        session.add(invoice)
        session.flush()

    with session_scope() as session:
        overview = fetch_district_vendor_overview(session, district.id)

    vendor_profile = overview.vendors[0]
    first_year = next(iter(vendor_profile.invoices))
    first_invoice = vendor_profile.invoices[first_year][0]

    assert first_invoice.month == "October"
    assert first_invoice.year == 2025
    assert first_invoice.download_url.endswith("&filename=INV-002.pdf")
