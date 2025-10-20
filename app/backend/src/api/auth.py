"""Authentication and authorization helpers."""

from fastapi import APIRouter, Depends

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me")
def read_current_user(user: dict | None = Depends(lambda: None)) -> dict[str, str | None]:
    """Return a placeholder current user response.

    The real implementation will depend on Auth0 JWT validation.
    """

    return {"message": "Auth0 integration pending", "user": user.get("sub") if user else None}
