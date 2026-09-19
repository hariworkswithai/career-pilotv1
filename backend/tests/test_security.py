"""Tests for security primitives: sanitization and token verification."""

from __future__ import annotations

import time

import jwt
import pytest

from app.core.security.auth import verify_access_token
from app.core.security.rate_limit import RateLimiter
from app.core.security.sanitize import sanitize_html


class TestSanitize:
    def test_scripts_and_handlers_removed(self):
        dirty = '<p>Hello <script>alert(1)</script></p><img src="x" onerror="alert(1)"><a href="javascript:alert(1)">bad</a><a href="https://ok.com">good</a>'
        clean = sanitize_html(dirty)
        assert "<script" not in clean
        assert "onerror" not in clean
        assert "javascript:" not in clean
        assert "https://ok.com" in clean

    def test_empty_input(self):
        assert sanitize_html("") == ""
        assert sanitize_html(None) == ""


class TestRateLimiter:
    def test_allows_up_to_max(self):
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        assert limiter.allow("u1") is True
        assert limiter.allow("u1") is True
        assert limiter.allow("u1") is True
        assert limiter.allow("u1") is False

    def test_separate_keys(self):
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        assert limiter.allow("a") is True
        assert limiter.allow("b") is True

    def test_window_resets(self):
        limiter = RateLimiter(max_requests=2, window_seconds=1)
        assert limiter.allow("k") is True
        assert limiter.allow("k") is True
        assert limiter.allow("k") is False
        time.sleep(1.1)
        assert limiter.allow("k") is True


class TestTokenVerification:
    def test_rs256_jwks_issuer_flow(self, monkeypatch):
        pytest.importorskip("cryptography")
        from cryptography.hazmat.primitives.asymmetric import rsa

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        jwk = _rsa_public_jwk(key.public_key())
        token = jwt.encode(
            {"sub": "supabase-user-1", "email": "a@b.co", "role": "authenticated", "aud": "authenticated", "exp": int(time.time() + 3600)},
            key,
            algorithm="RS256",
        )

        def fake_jwks(aud=None):
            return {"keys": [jwk]}

        monkeypatch.setattr("app.core.security.auth._fetch_jwks", fake_jwks)
        monkeypatch.setattr(
            "app.core.security.auth._issuer",
            lambda: _FakeIssuer(url="https://example.supabase.co", secret=""),
        )
        user = verify_access_token(token)
        assert user.user_id == "supabase-user-1"
        assert user.email == "a@b.co"

    def test_es256_jwks_issuer_flow(self, monkeypatch):
        pytest.importorskip("cryptography")
        from cryptography.hazmat.primitives.asymmetric import ec

        key = ec.generate_private_key(ec.SECP256R1())
        jwk = _ec_public_jwk(key.public_key())
        token = jwt.encode(
            {"sub": "supabase-user-ec", "email": "ec@b.co", "role": "authenticated", "aud": "authenticated", "exp": int(time.time() + 3600)},
            key,
            algorithm="ES256",
        )

        def fake_jwks(aud=None):
            return {"keys": [jwk]}

        monkeypatch.setattr("app.core.security.auth._fetch_jwks", fake_jwks)
        monkeypatch.setattr(
            "app.core.security.auth._issuer",
            lambda: _FakeIssuer(url="https://example.supabase.co", secret=""),
        )
        user = verify_access_token(token)
        assert user.user_id == "supabase-user-ec"
        assert user.email == "ec@b.co"

    def test_hs256_fallback_with_jwt_secret(self, monkeypatch):
        def fake_jwks(aud=None):
            return {"keys": []}

        monkeypatch.setattr("app.core.security.auth._fetch_jwks", fake_jwks)
        monkeypatch.setattr(
            "app.core.security.auth._issuer",
            lambda: _FakeIssuer(url="", secret="dev-secret"),
        )
        token = jwt.encode(
            {"sub": "user-2", "aud": "authenticated", "exp": int(time.time() + 3600)},
            "dev-secret",
            algorithm="HS256",
        )
        user = verify_access_token(token)
        assert user.user_id == "user-2"

    def test_invalid_token_raises_401(self, monkeypatch):
        def fake_jwks(aud=None):
            return {"keys": []}

        monkeypatch.setattr("app.core.security.auth._fetch_jwks", fake_jwks)
        import fastapi

        with pytest.raises(fastapi.HTTPException) as exc:
            verify_access_token("not.a.token")
        assert exc.value.status_code == 401


class _FakeIssuer:
    def __init__(self, url: str, secret: str) -> None:
        self.url = url
        self.secret = secret


def _rsa_public_jwk(public_key) -> dict:
    num = public_key.public_numbers()
    return {
        "kty": "RSA",
        "kid": "test",
        "use": "sig",
        "alg": "RS256",
        "n": b64enc(num.n),
        "e": b64enc(num.e),
    }


def _ec_public_jwk(public_key) -> dict:
    num = public_key.public_numbers()
    return {
        "kty": "EC",
        "kid": "test-ec",
        "use": "sig",
        "alg": "ES256",
        "crv": "P-256",
        "x": b64enc(num.x),
        "y": b64enc(num.y),
    }


def b64enc(value: int) -> str:
    import base64

    length = (value.bit_length() + 7) // 8
    data = value.to_bytes(length, "big")
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()
