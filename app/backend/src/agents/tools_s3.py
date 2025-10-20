"""Utility helpers for interacting with S3."""

from __future__ import annotations

from typing import Protocol


class S3Client(Protocol):
    """Protocol that documents the minimal client interface we rely on."""

    def upload_fileobj(self, fileobj, bucket: str, key: str, ExtraArgs: dict | None = None) -> None:  # noqa: N803
        """Upload a file-like object to S3."""

    def generate_presigned_url(self, client_method: str, Params: dict, ExpiresIn: int) -> str:  # noqa: N803
        """Generate a presigned S3 URL."""


def upload_file(client: S3Client, file_bytes: bytes, *, bucket: str, key: str) -> str:
    """Upload bytes to S3 and return the object key."""
    client.upload_fileobj(fileobj=memoryview(file_bytes), bucket=bucket, key=key, ExtraArgs={"ServerSideEncryption": "AES256"})
    return key


def presigned_url(client: S3Client, *, bucket: str, key: str, expires: int = 3600) -> str:
    """Return a pre-signed download URL."""
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires,
    )
