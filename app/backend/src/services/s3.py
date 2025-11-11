"""Minimal S3 client helpers."""

from __future__ import annotations

import mimetypes
import re
import shutil
import urllib.parse
from datetime import date, datetime
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import boto3
from botocore.client import BaseClient
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError
import structlog

from app.backend.src.core.config import get_settings

LOGGER = structlog.get_logger(__name__)


def _local_bucket_root() -> Path:
    settings = get_settings()
    root = Path(settings.local_storage_path)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _is_local_mode() -> bool:
    return get_settings().aws_s3_bucket.lower() == "local"


@lru_cache()
def _resolve_bucket_region() -> str | None:
    """Return the region for the configured S3 bucket."""

    settings = get_settings()

    if _is_local_mode():
        return None

    session_kwargs: dict[str, str] = {}
    if settings.aws_access_key_id and settings.aws_secret_access_key:
        session_kwargs["aws_access_key_id"] = settings.aws_access_key_id
        session_kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
    if settings.aws_region:
        session_kwargs["region_name"] = settings.aws_region

    try:
        session = boto3.session.Session(**session_kwargs)
        client = session.client("s3", config=Config(signature_version="s3v4"))
        response = client.get_bucket_location(Bucket=settings.aws_s3_bucket)
        region = response.get("LocationConstraint") or "us-east-1"
        if settings.aws_region and settings.aws_region != region:
            LOGGER.warning(
                "s3_region_mismatch",
                bucket=settings.aws_s3_bucket,
                configured=settings.aws_region,
                resolved=region,
            )
        else:
            LOGGER.info(
                "resolved_s3_region", bucket=settings.aws_s3_bucket, region=region
            )
        return region
    except (BotoCoreError, NoCredentialsError, ClientError) as exc:
        LOGGER.warning("resolve_s3_region_failed", error=str(exc))
        if settings.aws_region:
            LOGGER.info(
                "using_configured_region_fallback",
                bucket=settings.aws_s3_bucket,
                region=settings.aws_region,
            )
            return settings.aws_region
        return None


def _client() -> BaseClient:
    settings = get_settings()
    client_kwargs: dict[str, object] = {
        "config": Config(
            signature_version="s3v4",
            s3={"addressing_style": "virtual"},
        ),
    }

    resolved_region = settings.aws_region or _resolve_bucket_region() or "us-east-2"
    client_kwargs["region_name"] = resolved_region

    if settings.aws_access_key_id and settings.aws_secret_access_key:
        client_kwargs["aws_access_key_id"] = settings.aws_access_key_id
        client_kwargs["aws_secret_access_key"] = settings.aws_secret_access_key

    return boto3.client("s3", **client_kwargs)


def sanitize_company_name(company_name: str | None) -> str:
    """Return a deterministic, ASCII-only company segment for S3 paths."""

    raw_value = (company_name or "").strip()
    if not raw_value:
        return "unknown"

    ascii_value = raw_value.encode("ascii", errors="ignore").decode("ascii")
    sanitized = re.sub(r"[^A-Za-z0-9]+", "", ascii_value)
    return sanitized or "unknown"


def _normalize_reference_date(
    reference_date: date | datetime | str | None,
) -> datetime:
    """Return a timezone-naive datetime used for S3 path hierarchy."""

    if isinstance(reference_date, datetime):
        return reference_date
    if isinstance(reference_date, date):
        return datetime(reference_date.year, reference_date.month, reference_date.day)
    if isinstance(reference_date, str) and reference_date.strip():
        candidate = reference_date.strip()
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%Y-%m"):
            try:
                parsed = datetime.strptime(candidate, fmt)
                return parsed
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            pass
    return datetime.utcnow()


def _resolve_object_key(
    filename: str,
    *,
    key: str | None = None,
    company_name: str | None = None,
    reference_date: date | datetime | str | None = None,
) -> str:
    """Return a deterministic, S3-safe object key for the provided filename."""

    if key:
        return key

    safe_name = re.sub(r"[\\/]+", "_", filename).strip()
    safe_name = re.sub(r"_+", "_", safe_name)

    if company_name:
        normalized_company = sanitize_company_name(company_name)
        normalized_date = _normalize_reference_date(reference_date)
        year_segment = f"{normalized_date.year:04d}"
        month_segment = f"{normalized_date.month:02d}"
        hierarchical_key = (
            f"invoices/{normalized_company}/{year_segment}/{month_segment}/{safe_name}"
        )
        LOGGER.info(
            "s3_upload_path_updated",
            company=normalized_company,
            year=year_segment,
            month=month_segment,
            s3_key=hierarchical_key,
        )
        return hierarchical_key

    return f"invoices/{uuid4()}/{safe_name}"


def _determine_content_type(filename: str, content_type: str | None = None) -> str:
    """Infer a best-effort content type for uploads."""
    return (
        content_type
        or mimetypes.guess_type(filename)[0]
        or "application/octet-stream"
    )


def upload_file(
    file_path: Path,
    *,
    key: str | None = None,
    content_type: str | None = None,
    company_name: str | None = None,
    reference_date: date | datetime | str | None = None,
) -> str:
    """Upload a file to S3 or local storage and return the object key."""
    settings = get_settings()
    safe_filename = re.sub(r"[\\/]+", "_", file_path.name).strip()
    safe_filename = re.sub(r"_+", "_", safe_filename)
    object_key = _resolve_object_key(
        filename=safe_filename,
        key=key,
        company_name=company_name,
        reference_date=reference_date,
    )
    resolved_content_type = _determine_content_type(safe_filename, content_type)

    if _is_local_mode():
        destination = _local_bucket_root() / object_key
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(file_path, destination)
        LOGGER.info("stored_local", key=object_key, path=str(destination))
        return object_key

    try:
        client = _client()
        client.upload_file(
            Filename=str(file_path),
            Bucket=settings.aws_s3_bucket,
            Key=object_key,
            ExtraArgs={"ContentType": resolved_content_type},
        )
        LOGGER.info("uploaded_s3", bucket=settings.aws_s3_bucket, key=object_key)
        return object_key
    except (BotoCoreError, NoCredentialsError) as exc:
        LOGGER.error("s3_upload_failed", error=str(exc))
        raise


def upload_bytes(
    data: bytes,
    *,
    filename: str,
    key: str | None = None,
    content_type: str | None = None,
    company_name: str | None = None,
    reference_date: date | datetime | str | None = None,
) -> str:
    """Upload in-memory data to storage and return the object key."""
    settings = get_settings()
    safe_filename = re.sub(r"[\\/]+", "_", filename).strip()
    safe_filename = re.sub(r"_+", "_", safe_filename)
    object_key = _resolve_object_key(
        filename=safe_filename,
        key=key,
        company_name=company_name,
        reference_date=reference_date,
    )
    resolved_content_type = _determine_content_type(safe_filename, content_type)

    if _is_local_mode():
        destination = _local_bucket_root() / object_key
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        LOGGER.info("stored_local", key=object_key, path=str(destination))
        return object_key

    try:
        client = _client()
        client.upload_fileobj(
            Fileobj=BytesIO(data),
            Bucket=settings.aws_s3_bucket,
            Key=object_key,
            ExtraArgs={"ContentType": resolved_content_type},
        )
        LOGGER.info("uploaded_s3", bucket=settings.aws_s3_bucket, key=object_key)
        return object_key
    except (BotoCoreError, NoCredentialsError) as exc:
        LOGGER.error("s3_upload_failed", error=str(exc))
        raise


def sanitize_object_key(key: str) -> str:
    """Minimal, safe normalization that preserves exact S3 key semantics."""

    if not key:
        return ""

    sanitized = str(key).strip().strip('"').strip("'")
    sanitized = urllib.parse.unquote(sanitized)
    sanitized = re.sub(r"/+", "/", sanitized)
    if sanitized.startswith("/"):
        sanitized = sanitized[1:]
    return sanitized


def generate_presigned_url(
    key: str,
    *,
    expires_in: int = 3600,
    download_name: str | None = None,
    response_content_type: str | None = None,
) -> str:
    """Generate a presigned URL; optionally control the downloaded filename."""

    settings = get_settings()
    sanitized_key = sanitize_object_key(key)

    if _is_local_mode():
        return (_local_bucket_root() / sanitized_key).resolve().as_uri()

    params: dict[str, str] = {"Bucket": settings.aws_s3_bucket, "Key": sanitized_key}

    if download_name:
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", download_name)
        params["ResponseContentDisposition"] = f'attachment; filename="{safe_name}"'

    if response_content_type:
        params["ResponseContentType"] = response_content_type

    client = _client()
    LOGGER.info(
        "presign_debug",
        bucket=settings.aws_s3_bucket,
        region=settings.aws_region or client.meta.region_name,
        sanitized_key=sanitized_key,
        response_headers={k: v for k, v in params.items() if k.startswith("Response")},
    )
    return client.generate_presigned_url(
        "get_object",
        Params=params,
        ExpiresIn=expires_in,
    )


def get_s3_client() -> BaseClient:
    """Return a configured S3 client instance."""

    return _client()


__all__ = [
    "upload_file",
    "upload_bytes",
    "generate_presigned_url",
    "sanitize_object_key",
    "get_s3_client",
    "sanitize_company_name",
]
