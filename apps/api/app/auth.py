"""Clerk JWT verification — mirrors the reference project's api/auth.py:
RS256 against the issuer's JWKS via PyJWT, no Clerk SDK. Dependencies are sync
functions on purpose: FastAPI runs them in the threadpool, so the (cached,
occasionally refreshing) blocking JWKS fetch never blocks the event loop."""

from functools import lru_cache

import jwt
from fastapi import Depends, Header, HTTPException
from jwt import PyJWKClient

from .config import get_settings


def _issuer() -> str:
    issuer = get_settings().clerk_jwt_issuer.rstrip("/")
    if not issuer:
        raise HTTPException(status_code=500, detail="CLERK_JWT_ISSUER is not configured")
    return issuer


@lru_cache(maxsize=1)
def _jwks_client() -> PyJWKClient:
    return PyJWKClient(f"{_issuer()}/.well-known/jwks.json")


def _decode_payload(authorization: str | None, x_dev_user_id: str | None) -> dict:
    settings = get_settings()
    if settings.clerk_auth_disabled:
        # Local dev only. X-Dev-User-Id lets you act as different parents.
        return {"sub": x_dev_user_id or "dev-parent"}

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()

    try:
        signing_key = _jwks_client().get_signing_key_from_jwt(token).key
        decode_kwargs: dict = {
            "algorithms": ["RS256"],
            "issuer": _issuer(),
            "options": {"require": ["exp", "iat", "sub", "iss"]},
        }
        audience = get_settings().clerk_audience
        if audience:
            decode_kwargs["audience"] = audience
        else:
            decode_kwargs["options"]["verify_aud"] = False
        return jwt.decode(token, signing_key, **decode_kwargs)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}") from exc


def require_parent(
    authorization: str | None = Header(default=None),
    x_dev_user_id: str | None = Header(default=None),
) -> str:
    """Returns the Clerk user id (`sub`) of the signed-in parent."""
    payload = _decode_payload(authorization, x_dev_user_id)
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Token has no subject")
    return str(sub)


def require_admin(user_id: str = Depends(require_parent)) -> str:
    """Parent must additionally appear in the ADMIN_CLERK_USER_IDS allowlist."""
    settings = get_settings()
    if settings.clerk_auth_disabled:
        return user_id
    if user_id not in settings.admin_user_ids:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user_id
