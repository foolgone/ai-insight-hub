"""B-208 JWT 与密码哈希单测。"""
from __future__ import annotations

import pytest

from app.core.config import settings
from app.core.exceptions import RefreshTokenInvalidError, TokenExpiredError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    token_remaining_seconds,
    verify_password,
)

pytestmark = pytest.mark.unit


def test_password_hash_roundtrip() -> None:
    password_hash = hash_password("secret123")

    assert password_hash != "secret123"
    assert password_hash.startswith("$2")
    assert verify_password("secret123", password_hash) is True
    assert verify_password("wrong-password", password_hash) is False


def test_verify_password_with_invalid_hash() -> None:
    assert verify_password("secret123", "not-a-bcrypt-hash") is False


def test_access_token_claims() -> None:
    token, jti, _ = create_access_token("user-1", "admin")
    payload = decode_token(token, "access")

    assert payload["sub"] == "user-1"
    assert payload["role"] == "admin"
    assert payload["type"] == "access"
    assert payload["jti"] == jti
    assert token_remaining_seconds(payload) > 0


def test_refresh_token_claims() -> None:
    token, _, _ = create_refresh_token("user-2", "user")
    payload = decode_token(token, "refresh")

    assert payload["sub"] == "user-2"
    assert payload["type"] == "refresh"


def test_token_type_must_match_expected() -> None:
    refresh_token, _, _ = create_refresh_token("user-1", "user")
    with pytest.raises(TokenExpiredError):
        decode_token(refresh_token, "access")

    access_token, _, _ = create_access_token("user-1", "user")
    with pytest.raises(RefreshTokenInvalidError):
        decode_token(access_token, "refresh")


def test_tampered_token_rejected() -> None:
    with pytest.raises(TokenExpiredError):
        decode_token("not.a.valid-token", "access")


def test_expired_access_token_rejected(monkeypatch) -> None:
    monkeypatch.setattr(settings, "JWT_ACCESS_TOKEN_EXPIRE_MINUTES", -1)
    token, _, _ = create_access_token("user-1", "user")

    with pytest.raises(TokenExpiredError):
        decode_token(token, "access")


def test_expired_refresh_token_rejected(monkeypatch) -> None:
    monkeypatch.setattr(settings, "JWT_REFRESH_TOKEN_EXPIRE_DAYS", -1)
    token, _, _ = create_refresh_token("user-1", "user")

    with pytest.raises(RefreshTokenInvalidError):
        decode_token(token, "refresh")
