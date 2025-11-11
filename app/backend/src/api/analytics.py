"""Analytics endpoints for district reviewers."""

from fastapi import APIRouter, Depends

from app.backend.src.core.security import require_district_user
from app.backend.src.models import User

router = APIRouter(prefix="/stats", tags=["analytics"])


@router.get("/summary")
async def get_summary(_: User = Depends(require_district_user)) -> dict[str, int]:
    """Return placeholder analytics metrics."""
    return {"total_invoices": 0, "approved": 0, "pending": 0}
