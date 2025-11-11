"""Upload management endpoints."""

from fastapi import APIRouter, Depends, UploadFile

from app.backend.src.core.security import require_vendor_user
from app.backend.src.models import User

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("")
async def create_upload(
    file: UploadFile,
    _: User = Depends(require_vendor_user),
) -> dict[str, str]:
    """Stub endpoint that accepts a file and returns a placeholder job id."""
    return {"job_id": "pending", "filename": file.filename}


@router.get("/{upload_id}/status")
async def get_upload_status(
    upload_id: str,
    _: User = Depends(require_vendor_user),
) -> dict[str, str]:
    """Return a static upload status placeholder."""
    return {"upload_id": upload_id, "status": "queued"}
