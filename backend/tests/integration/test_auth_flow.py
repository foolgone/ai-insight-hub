"""B-208 认证流程集成测试（真实 PostgreSQL + Redis）。"""
from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.integration

PASSWORD = "secret123"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _register(client, *, password: str = PASSWORD) -> tuple[str, dict]:
    email = f"auth-{uuid.uuid4().hex[:10]}@example.com"
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "name": "Auth User"},
    )
    assert response.status_code == 201, response.text
    return email, response.json()


async def _login(client, email: str, password: str = PASSWORD) -> dict:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


async def test_register_returns_user_with_snake_case(client) -> None:
    email, user = await _register(client)

    assert user["email"] == email
    assert user["role"] == "user"
    assert "created_at" in user
    assert "avatarUrl" not in user


async def test_register_duplicate_email_conflict(client) -> None:
    email, _ = await _register(client)

    response = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": PASSWORD}
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "USER_EMAIL_EXISTS"


async def test_register_rejects_short_password(client) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": f"short-{uuid.uuid4().hex[:8]}@example.com", "password": "123"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_login_with_wrong_password(client) -> None:
    email, _ = await _register(client)

    response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "wrong-password"}
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_INVALID_CREDENTIALS"


async def test_login_returns_token_pair(client) -> None:
    email, _ = await _register(client)
    tokens = await _login(client, email)

    assert tokens["token_type"] == "bearer"
    assert tokens["expires_in"] == 3600
    assert tokens["refresh_expires_in"] == 604800
    assert tokens["user"]["email"] == email


async def test_me_requires_access_token(client) -> None:
    response = await client.get("/api/v1/users/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_TOKEN_EXPIRED"

    response = await client.get("/api/v1/users/me", headers=_auth("not-a-valid-token"))
    assert response.status_code == 401


async def test_refresh_rotates_and_revokes_old_token(client) -> None:
    email, _ = await _register(client)
    tokens = await _login(client, email)

    refreshed = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refreshed.status_code == 200, refreshed.text
    new_tokens = refreshed.json()
    assert new_tokens["access_token"] != tokens["access_token"]
    assert new_tokens["refresh_token"] != tokens["refresh_token"]

    reused = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert reused.status_code == 401
    assert reused.json()["error"]["code"] == "AUTH_REFRESH_TOKEN_INVALID"

    me = await client.get("/api/v1/users/me", headers=_auth(new_tokens["access_token"]))
    assert me.status_code == 200


async def test_logout_revokes_both_tokens(client) -> None:
    email, _ = await _register(client)
    tokens = await _login(client, email)

    response = await client.post(
        "/api/v1/auth/logout",
        headers=_auth(tokens["access_token"]),
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Logged out"

    me = await client.get("/api/v1/users/me", headers=_auth(tokens["access_token"]))
    assert me.status_code == 401
    assert me.json()["error"]["code"] == "AUTH_TOKEN_EXPIRED"

    refreshed = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refreshed.status_code == 401
    assert refreshed.json()["error"]["code"] == "AUTH_REFRESH_TOKEN_INVALID"
