import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

sys.path.append(str(Path(__file__).resolve().parents[4]))

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_invoice.db")

import pytest

from app.backend.src.services import s3


def test_generate_presigned_url_uses_sigv4(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_config = None

    settings = SimpleNamespace(
        aws_region="us-east-1",
        aws_s3_bucket="invoice-agent-files",
        aws_access_key_id="test",
        aws_secret_access_key="secret",
        local_storage_path="/tmp/invoice-agent",
    )

    def fake_boto3_client(service_name: str, **kwargs: object) -> Mock:
        nonlocal captured_config
        captured_config = kwargs.get("config")
        mock_client = Mock()
        mock_client.generate_presigned_url.return_value = "https://example.com/presigned"
        return mock_client

    monkeypatch.setattr(s3, "get_settings", lambda: settings)
    monkeypatch.setattr(s3.boto3, "client", fake_boto3_client)

    url = s3.generate_presigned_url("invoices/example.pdf")

    assert url == "https://example.com/presigned"
    assert captured_config is not None
    assert getattr(captured_config, "signature_version", None) == "s3v4"
