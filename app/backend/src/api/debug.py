"""Debug endpoints for troubleshooting integrations."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.backend.src.core.security import require_role
from app.backend.src.models import User
from app.backend.src.services import s3

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/presign")
def debug_presign(
    key: str = Query(..., min_length=1, description="S3 object key to presign"),
    expires_in: int = Query(
        3600,
        ge=60,
        le=86400,
        description="Expiration time in seconds for the presigned URL.",
    ),
    _: User = Depends(require_role({"vendor", "district"})),
) -> dict[str, str | int]:
    """Return a presigned URL for the provided key without fetching the object."""

    sanitized_key = s3.sanitize_object_key(key)
    url = s3.generate_presigned_url(key=key, expires_in=expires_in)
    return {
        "raw_key": key,
        "sanitized_key": sanitized_key,
        "expires_in": expires_in,
        "url": url,
    }
