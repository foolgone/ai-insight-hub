"""B-209/B-210 用户模块与 RBAC 集成测试。"""
from __future__ import annotations

import uuid

import pytest

from app.core.security import hash_password
from tests.factories import UserFactory, persist

pytestmark = pytest.mark.integration

PASSWORD = "secret123"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _register_and_login(client) -> tuple[str, dict]:
    email = f"user-{uuid.uuid4().hex[:10]}@example.com"
    registered = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD, "name": "User"},
    )
    assert registered.status_code == 201, registered.text
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200, login.text
    return email, login.json()


async def test_get_me_returns_profile_with_quota(client) -> None:
    email, tokens = await _register_and_login(client)

    response = await client.get("/api/v1/users/me", headers=_auth(tokens["access_token"]))

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == email
    assert body["role"] == "user"
    assert body["is_active"] is True
    assert body["quota"]["max_datasources"] == 10
    assert body["usage"]["datasources_count"] == 0


async def test_update_profile_is_partial(client) -> None:
    email, tokens = await _register_and_login(client)
    headers = _auth(tokens["access_token"])

    updated = await client.patch("/api/v1/users/me", headers=headers, json={"name": "新名字"})
    assert updated.status_code == 200
    body = updated.json()
    assert body["name"] == "新名字"
    assert body["avatar_url"] is None
    assert "avatarUrl" not in body

    avatar = await client.patch(
        "/api/v1/users/me",
        headers=headers,
        json={"avatar_url": "https://example.com/a.png"},
    )
    assert avatar.status_code == 200
    assert avatar.json()["avatar_url"] == "https://example.com/a.png"
    assert avatar.json()["name"] == "新名字"  # 未传字段保持不变


async def test_change_password_flow(client) -> None:
    email, tokens = await _register_and_login(client)
    headers = _auth(tokens["access_token"])

    wrong = await client.post(
        "/api/v1/users/me/password",
        headers=headers,
        json={"current_password": "wrong-pass", "new_password": "newsecret123"},
    )
    assert wrong.status_code == 400
    assert wrong.json()["error"]["code"] == "BAD_REQUEST"

    ok = await client.post(
        "/api/v1/users/me/password",
        headers=headers,
        json={"current_password": PASSWORD, "new_password": "newsecret123"},
    )
    assert ok.status_code == 200

    old_login = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert old_login.status_code == 401

    new_login = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "newsecret123"}
    )
    assert new_login.status_code == 200


async def test_viewer_is_read_only(client, db_session) -> None:
    email = f"viewer-{uuid.uuid4().hex[:8]}@example.com"
    viewer = UserFactory(email=email, password_hash=hash_password("viewer123"), role="viewer")
    await persist(db_session, viewer)

    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "viewer123"})
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    headers = _auth(token)

    read = await client.get("/api/v1/users/me", headers=headers)
    assert read.status_code == 200

    patch = await client.patch("/api/v1/users/me", headers=headers, json={"name": "viewer-edit"})
    assert patch.status_code == 403
    assert patch.json()["error"]["code"] == "AUTH_FORBIDDEN"

    password = await client.post(
        "/api/v1/users/me/password",
        headers=headers,
        json={"current_password": "viewer123", "new_password": "viewer456"},
    )
    assert password.status_code == 403
