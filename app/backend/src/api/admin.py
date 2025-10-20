"""Administrative endpoints for managing datasets, users, and vendors."""

from fastapi import APIRouter

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/seed")
async def load_seed_data() -> dict[str, str]:
    """Return a placeholder response acknowledging the seed action."""
    return {"status": "seeded"}
