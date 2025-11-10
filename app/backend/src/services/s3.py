"""Minimal S3 client helpers."""

from __future__ import annotations

from io import BytesIO
import mimetypes
import shutil
from pathlib import Path
from uuid import uuid4

import boto3
from botocore.client import BaseClient
from botocore.config import Config
from botocore.exceptions import BotoCoreError, NoCredentialsError
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


def _client() -> BaseClient:
    settings = get_settings()
    return boto3.client(
        "s3",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        config=Config(signature_version="s3v4"),
    )


def _resolve_object_key(filename: str, key: str | None = None) -> str:
    """Return a deterministic object key for the provided filename."""

    if key:
        return key
    return f"invoices/{uuid4()}/{filename}"


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
) -> str:
    """Upload a file to S3 or local storage and return the object key."""

    settings = get_settings()
    object_key = _resolve_object_key(file_path.name, key=key)
    resolved_content_type = _determine_content_type(file_path.name, content_type)

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
) -> str:
    """Upload in-memory data to storage and return the object key."""

    settings = get_settings()
    object_key = _resolve_object_key(filename, key=key)
    resolved_content_type = _determine_content_type(filename, content_type)

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


def generate_presigned_url(key: str, expires_in: int = 3600) -> str:
    """Generate a presigned URL for the provided object key."""

    settings = get_settings()
    if _is_local_mode():
        path = _local_bucket_root() / key
        return path.as_uri()

    client = _client()
    try:
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.aws_s3_bucket, "Key": key},
            ExpiresIn=expires_in,
        )
    except (BotoCoreError, NoCredentialsError) as exc:
        LOGGER.error("presign_failed", error=str(exc), key=key)
        raise


__all__ = ["upload_file", "upload_bytes", "generate_presigned_url"]
