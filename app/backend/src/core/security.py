"""Security helpers for Auth0 integration."""

from __future__ import annotations

print(">>> LOADED security.py from:", __file__, flush=True)

from functools import lru_cache
from typing import Any, Iterable
import sys
import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.backend.src.core.config import get_settings
from ..db import get_session_dependency
from app.backend.src.models import User
from app.backend.src.models.vendor import Vendor

ALGORITHMS = ["RS256"]
_scheme = HTTPBearer(auto_error=False)


# -------------------------------------------------------
# JWKS + Token Utilities
# -------------------------------------------------------

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
    except JWTError as exc:
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


def _normalize_audience_values(values: Iterable[str]) -> list[str]:
    """Return a list of canonical audience strings with slash variants."""
    normalized: list[str] = []
    for value in values:
        candidate = value.strip()
        if not candidate:
            continue

        trimmed = candidate.rstrip("/")
        for option in (candidate, trimmed, f"{trimmed}/" if trimmed else ""):
            if option and option not in normalized:
                normalized.append(option)
    return normalized


def _collect_audience_values(raw_value: str | None) -> list[str]:
    """Split the configured audience string into individual values."""
    if not raw_value:
        return []
    candidates = [segment for segment in raw_value.replace("\n", " ").split() if segment]
    expanded: list[str] = []
    for candidate in candidates:
        for part in candidate.split(","):
            value = part.strip()
            if value and value not in expanded:
                expanded.append(value)
    return expanded


def _decode_token(token: str, *, domain: str, audiences: list[str]) -> dict[str, Any]:
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
            issuer=f"https://{domain}/",
            options={"verify_aud": False},
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from exc

    token_audiences: list[str] = []
    audience_claim = payload.get("aud")
    if isinstance(audience_claim, str):
        token_audiences.append(audience_claim)
    elif isinstance(audience_claim, (list, tuple, set)):
        for entry in audience_claim:
            if isinstance(entry, str):
                token_audiences.append(entry)
    if not token_audiences:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing audience",
        )

    normalized_token_audiences = set(_normalize_audience_values(token_audiences))
    normalized_allowed_audiences = set(_normalize_audience_values(audiences))
    if not normalized_token_audiences & normalized_allowed_audiences:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token audience",
        )

    print("DEBUG: Decoded token successfully", file=sys.stdout, flush=True)
    return payload


# -------------------------------------------------------
# User Resolution
# -------------------------------------------------------

def _ensure_vendor_record(session: Session, user: User) -> None:
    """Ensure a vendor record exists for the given vendor user."""

    if (user.role or "").lower() != "vendor":
        return

    vendor = user.vendor
    changed = False

    if vendor is None:
        vendor = (
            session.query(Vendor)
            .filter(Vendor.contact_email == user.email)
            .one_or_none()
        )
        if vendor is None:
            vendor = Vendor(
                company_name=user.name or user.email,
                contact_name=user.name or user.email,
                contact_email=user.email,
                phone_number="N/A",
                remit_to_street="N/A",
                remit_to_city="N/A",
                remit_to_state="NA",
                remit_to_postal_code="00000",
            )
            session.add(vendor)
            session.flush()
            print(
                f"[auto-create] Vendor record created for {user.email}",
                flush=True,
            )
            changed = True
        if user.vendor_id != vendor.id:
            user.vendor_id = vendor.id
            session.add(user)
            changed = True

    if changed:
        session.commit()


def _resolve_user(session: Session, payload: dict[str, Any]) -> User:
    """Map a verified Auth0 payload to an application user."""
    print("DEBUG: Entering _resolve_user", file=sys.stdout, flush=True)
    subject = payload.get("sub")
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject",
        )

    # Try lookup by Auth0 subject
    user = session.query(User).filter(User.auth0_sub == subject).one_or_none()
    if user:
        print("DEBUG: _resolve_user returning existing:", user.email, user.role, file=sys.stdout, flush=True)
        _ensure_vendor_record(session, user)
        return user

    # Lookup by email (with namespaced support)
    email = payload.get("email") or payload.get("https://invoice-api/email")

    if email:
        user = session.query(User).filter(User.email == email).one_or_none()
        if user:
            if user.auth0_sub != subject:
                user.auth0_sub = subject
                session.add(user)
                session.commit()
            print("DEBUG: _resolve_user linked email to sub:", user.email, user.role, file=sys.stdout, flush=True)
            _ensure_vendor_record(session, user)
            return user

    if not email:
        print("DEBUG: Token missing email; cannot link user", file=sys.stdout, flush=True)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User record not found",
        )

    # If not found, create user
    display_name = (payload.get("name") or payload.get("nickname") or email).strip()
    user = User(email=email, name=display_name, role=None, auth0_sub=subject)
    session.add(user)
    session.commit()
    print("DEBUG: _resolve_user created new user:", user.email, user.role, file=sys.stdout, flush=True)
    _ensure_vendor_record(session, user)
    return user


# -------------------------------------------------------
# Current User + Role Enforcement
# -------------------------------------------------------

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

    configured_audiences = _collect_audience_values(settings.auth0_audience)
    if not configured_audiences:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Auth0 configuration is invalid",
        )

    payload = _decode_token(
        credentials.credentials,
        domain=settings.auth0_domain,
        audiences=configured_audiences,
    )
    user = _resolve_user(session, payload)

    print(
        "DEBUG-USER:",
        user.email,
        "| role:", user.role,
        "| approved:", getattr(user, "is_approved", None),
        "| active:", getattr(user, "is_active", None),
        file=sys.stdout,
        flush=True,
    )

    # Account state checks
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    if not user.is_approved and (not user.role or user.role.lower() != "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account pending approval",
        )

    return user


def _enforce_roles(user: User, allowed_roles: set[str], *, allow_admin: bool = True) -> User:
    """Ensure the authenticated user has one of the allowed roles."""
    role = (user.role or "").lower()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User role not assigned",
        )

    normalized_allowed = {value.lower() for value in allowed_roles}
    if role in normalized_allowed:
        return user
    if allow_admin and role == "admin":
        return user
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Insufficient permissions",
    )


def require_vendor_user(user: User = Depends(get_current_user)) -> User:
    """Dependency ensuring the caller is a vendor or admin user."""
    return _enforce_roles(user, {"vendor"})


def require_district_user(user: User = Depends(get_current_user)) -> User:
    """Dependency ensuring the caller is a district or admin user."""
    return _enforce_roles(user, {"district"})


def require_admin_user(user: User = Depends(get_current_user)) -> User:
    """Dependency ensuring the caller is an administrator."""
    return _enforce_roles(user, {"admin"}, allow_admin=False)


def require_role(
    roles: Iterable[str],
    *,
    allow_admin: bool = True,
):
    """Return a dependency that enforces one of the provided roles."""
    normalized_roles = {value.lower() for value in roles}

    def dependency(user: User = Depends(get_current_user)) -> User:
        return _enforce_roles(user, normalized_roles, allow_admin=allow_admin)

    return dependency


__all__ = [
    "get_current_user",
    "require_admin_user",
    "require_district_user",
    "require_vendor_user",
    "require_role",
]
