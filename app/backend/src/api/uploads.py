"""Upload management endpoints."""

from fastapi import APIRouter, UploadFile

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("")
async def create_upload(file: UploadFile) -> dict[str, str]:
    """Stub endpoint that accepts a file and returns a placeholder job id."""
    return {"job_id": "pending", "filename": file.filename}


@router.get("/{upload_id}/status")
async def get_upload_status(upload_id: str) -> dict[str, str]:
    """Return a static upload status placeholder."""
    return {"upload_id": upload_id, "status": "queued"}
