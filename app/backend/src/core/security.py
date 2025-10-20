"""Security helpers for Auth0 integration."""

from fastapi import Depends


def auth_dependency() -> dict:
    """Placeholder dependency representing the authenticated user."""

    return {"sub": "auth0|placeholder"}


def require_role(required_role: str):
    """Return a dependency that would enforce RBAC."""

    def dependency(user: dict = Depends(auth_dependency)) -> dict:
        if user.get("role") != required_role:
            raise PermissionError("RBAC enforcement not yet implemented")
        return user

    return dependency
