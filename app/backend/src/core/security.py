"""Security helpers for Auth0 integration."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.backend.src.core.config import get_settings
from app.backend.src.db import get_session_dependency
from app.backend.src.models import User

ALGORITHMS = ["RS256"]
_scheme = HTTPBearer(auto_error=False)


@lru_cache()
def _fetch_jwks(domain: str) -> dict[str, Any]:
    """Fetch (and cache) the JWKS for the given Auth0 domain."""

    jwks_url = f"https://{domain}/.well-known/jwks.json"
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(jwks_url)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to retrieve JWKS",
        ) from exc


def _get_rsa_key(token: str, domain: str) -> dict[str, str] | None:
    """Return the RSA key that matches the token header."""

    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError as exc:  # pragma: no cover - invalid header formatting
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header",
        ) from exc

    if "kid" not in unverified_header:
        return None

    jwks = _fetch_jwks(domain)
    for key in jwks.get("keys", []):
        if key.get("kid") == unverified_header["kid"]:
            return {
                "kty": key.get("kty"),
                "kid": key.get("kid"),
                "use": key.get("use"),
                "n": key.get("n"),
                "e": key.get("e"),
            }
    return None


def _decode_token(token: str, *, domain: str, audience: str) -> dict[str, Any]:
    """Decode and validate an Auth0 access token."""

    rsa_key = _get_rsa_key(token, domain)
    if not rsa_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unable to validate token",
        )

    try:
        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=ALGORITHMS,
            audience=audience,
            issuer=f"https://{domain}/",
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from exc

    return payload


def _resolve_user(session: Session, payload: dict[str, Any]) -> User:
    """Map a verified Auth0 payload to an application user."""

    subject = payload.get("sub")
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject",
        )

    user = session.query(User).filter(User.auth0_sub == subject).one_or_none()
    if user:
        return user

    email = payload.get("email")
    if email:
        user = session.query(User).filter(User.email == email).one_or_none()
        if user:
            user.auth0_sub = subject
            session.add(user)
            session.flush()
            return user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="User record not found",
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_scheme),
    session: Session = Depends(get_session_dependency),
) -> User:
    """Resolve the authenticated user from the Auth0 bearer token."""

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing",
        )

    settings = get_settings()
    if not settings.auth0_domain or not settings.auth0_audience:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Auth0 configuration is incomplete",
        )

    payload = _decode_token(
        credentials.credentials,
        domain=settings.auth0_domain,
        audience=settings.auth0_audience,
    )
    return _resolve_user(session, payload)


__all__ = ["get_current_user"]
