"""Analytics endpoints for district reviewers."""

from fastapi import APIRouter

router = APIRouter(prefix="/stats", tags=["analytics"])


@router.get("/summary")
async def get_summary() -> dict[str, int]:
    """Return placeholder analytics metrics."""
    return {"total_invoices": 0, "approved": 0, "pending": 0}
