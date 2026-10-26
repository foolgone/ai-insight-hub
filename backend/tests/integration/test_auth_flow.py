"""B-208 认证流程集成测试（真实 PostgreSQL + Redis）。

T4（2026-10-26）：refresh token 只走 HttpOnly Cookie，响应体不再返回 refresh_token。
"""
from __future__ import annotations

import uuid

import pytest

from app.core.config import settings

pytestmark = pytest.mark.integration

PASSWORD = "secret123"
REFRESH_PATH = "/api/v1/auth/refresh"


@pytest.fixture(autouse=True)
def _cookie_over_http(monkeypatch) -> None:
    """测试走 http://testserver：强制 Secure=False，避免 Cookie 被客户端丢弃。"""
    monkeypatch.setattr(settings, "AUTH_COOKIE_SECURE", False)


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


async def _login_response(client, email: str, password: str = PASSWORD):
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response


async def _login(client, email: str, password: str = PASSWORD) -> dict:
    return (await _login_response(client, email, password)).json()


def _refresh_cookie(client) -> str | None:
    return client.cookies.get(settings.AUTH_COOKIE_NAME)


async def _refresh(client, *, cookie: str | None = None):
    kwargs = {"cookies": {settings.AUTH_COOKIE_NAME: cookie}} if cookie else {}
    return await client.post(REFRESH_PATH, **kwargs)


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


async def test_login_sets_httponly_refresh_cookie(client) -> None:
    email, _ = await _register(client)
    response = await _login_response(client, email)
    body = response.json()

    # 响应体不再返回 refresh_token（字段保留为 null 兼容旧客户端）
    assert body.get("refresh_token") is None
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 3600
    assert body["refresh_expires_in"] == settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600
    assert body["user"]["email"] == email

    set_cookie = response.headers.get("set-cookie", "")
    assert settings.AUTH_COOKIE_NAME in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie
    assert f"Path={settings.AUTH_COOKIE_PATH}" in set_cookie
    assert _refresh_cookie(client), "HttpOnly Cookie 应写入客户端 Cookie 罐"


async def test_me_requires_access_token(client) -> None:
    response = await client.get("/api/v1/users/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_TOKEN_EXPIRED"

    response = await client.get("/api/v1/users/me", headers=_auth("not-a-valid-token"))
    assert response.status_code == 401


async def test_refresh_rotates_cookie_and_revokes_old_token(client) -> None:
    email, _ = await _register(client)
    tokens = await _login(client, email)
    old_cookie = _refresh_cookie(client)
    assert old_cookie

    refreshed = await _refresh(client)
    assert refreshed.status_code == 200, refreshed.text
    new_tokens = refreshed.json()
    assert new_tokens["access_token"] != tokens["access_token"]
    new_cookie = _refresh_cookie(client)
    assert new_cookie and new_cookie != old_cookie

    # 旧 Cookie 已轮换 → 重放应 401
    reused = await _refresh(client, cookie=old_cookie)
    assert reused.status_code == 401
    assert reused.json()["error"]["code"] == "AUTH_REFRESH_TOKEN_INVALID"

    me = await client.get("/api/v1/users/me", headers=_auth(new_tokens["access_token"]))
    assert me.status_code == 200


async def test_refresh_without_cookie_returns_401(client) -> None:
    response = await client.post(REFRESH_PATH)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REFRESH_TOKEN_INVALID"


async def test_refresh_accepts_body_fallback_for_non_browser_clients(client) -> None:
    email, _ = await _register(client)
    await _login(client, email)
    cookie = _refresh_cookie(client)

    # 模拟非浏览器客户端：清空 Cookie 罐，只用请求体传 refresh_token
    client.cookies.clear()
    response = await client.post(REFRESH_PATH, json={"refresh_token": cookie})

    assert response.status_code == 200, response.text
    assert response.json()["access_token"]


async def test_logout_revokes_tokens_and_clears_cookie(client) -> None:
    email, _ = await _register(client)
    tokens = await _login(client, email)
    cookie = _refresh_cookie(client)

    response = await client.post("/api/v1/auth/logout", headers=_auth(tokens["access_token"]))
    assert response.status_code == 200
    assert response.json()["message"] == "Logged out"
    assert _refresh_cookie(client) in (None, "")

    me = await client.get("/api/v1/users/me", headers=_auth(tokens["access_token"]))
    assert me.status_code == 401
    assert me.json()["error"]["code"] == "AUTH_TOKEN_EXPIRED"

    refreshed = await _refresh(client, cookie=cookie)
    assert refreshed.status_code == 401
    assert refreshed.json()["error"]["code"] == "AUTH_REFRESH_TOKEN_INVALID"
