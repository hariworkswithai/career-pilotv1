"""Supabase JWT verification for the FastAPI backend.

Tokens are verified with the Supabase JWKS (RS256) when available, falling back to
HS256 verification with SUPABASE_JWT_SECRET for local development. The user identity
is never trusted from the client beyond what the signature guarantees.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import httpx
import jwt
from fastapi import Depends, Header, HTTPException, status
from pydantic import BaseModel

from app.core.config import get_settings
from app.db import get_repository
from app.db.base import Repository


class VerifiedUser(BaseModel):
    user_id: str
    email: str = ""
    role: str = "authenticated"


@dataclass(frozen=True)
class _Issuer:
    url: str
    secret: str


def _issuer() -> _Issuer:
    s = get_settings()
    return _Issuer(url=s.supabase_url.rstrip("/") if s.supabase_url else "", secret=s.supabase_jwt_secret)


def _fetch_jwks(aud: str | None = None) -> dict:
    url = _issuer().url
    if not url:
        return {}
    try:
        with httpx.Client(timeout=5) as client:
            resp = client.get(f"{url}/auth/v1/.well-known/jwks.json")
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError:
        return {}


def _jwk_key_and_algorithms(key: dict) -> tuple[object, list[str]]:
    """Return a PyJWT-ready public key and allowed algorithms for a JWKS entry.

    Supabase projects may sign access tokens with either an RSA (RS256) or an
    Elliptic Curve (ES256) key depending on when the project was created, so we
    dispatch on the JWK ``kty``/``alg`` instead of assuming RS256.
    """
    kty = str(key.get("kty", ""))
    alg = str(key.get("alg", ""))
    if kty == "RSA" or alg.startswith("RS"):
        return jwt.algorithms.RSAAlgorithm.from_jwk(key), ["RS256"]
    if kty == "EC" or alg.startswith("ES"):
        return jwt.algorithms.ECAlgorithm.from_jwk(key), [alg] if alg.startswith("ES") else ["ES256"]
    return None, []


def verify_access_token(token: str) -> VerifiedUser:
    """Verify a Supabase access token and return the user identity.

    Raises HTTP 401 for any invalid/expired token. Never logs the token.
    """
    issuer = _issuer()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing access token")

    try:
        unverified = jwt.decode(token, options={"verify_signature": False})
        aud = unverified.get("aud", "authenticated")
        jwks = _fetch_jwks() if issuer.url else {}
        keys = jwks.get("keys", []) if jwks else []
        last_error: Exception | None = None

        for key in keys:
            public_key, algorithms = _jwk_key_and_algorithms(key)
            if public_key is None:
                continue
            try:
                payload = jwt.decode(
                    token,
                    cast(jwt.PyJWK, public_key),
                    algorithms=algorithms,
                    audience=aud,
                    options={"require": ["sub", "exp"]},
                )
                return VerifiedUser(
                    user_id=payload["sub"],
                    email=payload.get("email", ""),
                    role=payload.get("role", "authenticated"),
                )
            except jwt.PyJWTError as exc:  # noqa: PERF203
                last_error = exc

        # HS256 fallback for local dev / self-hosted secrets.
        if issuer.secret:
            payload = jwt.decode(
                token,
                issuer.secret,
                algorithms=["HS256"],
                audience=aud,
                options={"require": ["sub", "exp"]},
            )
            return VerifiedUser(
                user_id=payload["sub"],
                email=payload.get("email", ""),
                role=payload.get("role", "authenticated"),
            )
        if last_error:
            raise last_error
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")


async def current_user(authorization: str | None = Header(default=None)) -> VerifiedUser:
    """FastAPI dependency: require a valid Bearer token."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Bearer token")
    return verify_access_token(authorization.split(" ", 1)[1].strip())


async def require_admin(
    user: VerifiedUser = Depends(current_user),  # noqa: B008
    repository: Repository = Depends(get_repository),  # noqa: B008
) -> VerifiedUser:
    """FastAPI dependency: authenticated user with the admin role.

    Authorization is enforced server-side, never by hiding UI.
    """
    if not repository.is_admin(user.user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user
