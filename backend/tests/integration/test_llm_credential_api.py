"""BYOK 凭据 API 集成测试（AC-BK-03/04/06/09/10/11/14 + 428 守门 + 开关矩阵）。

依赖真实 PostgreSQL（docker-compose.test.yml）；沿用 ``tests/integration/conftest.py``
的 ``client`` / ``db_session`` / ``test_user`` / ``auth_headers``。
"""
from __future__ import annotations

import re
import uuid

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select

from app.core.config import settings
from app.models.security import AuditLog
from app.services.credential_service import credential_service

pytestmark = pytest.mark.integration

KEY = "sk-userkey0000000000"
PLAINTEXT_PATTERN = re.compile(r"sk-[A-Za-z0-9]{10,}")


@pytest.fixture(autouse=True)
def byok_env(monkeypatch):
    """BYOK 打开、不允许回退（本文件专门验证 428/400 语义）。"""
    monkeypatch.setattr(settings, "BYOK_ENABLED", True)
    monkeypatch.setattr(settings, "ALLOW_SERVER_KEY_FALLBACK", False)
    monkeypatch.setattr(settings, "CREDENTIAL_ENCRYPTION_KEY", Fernet.generate_key().decode())


@pytest.fixture(autouse=True)
def no_real_verify(monkeypatch):
    async def _ok(_api_key: str) -> bool:
        return True

    monkeypatch.setattr(credential_service, "verify", _ok)


async def test_put_get_delete_roundtrip(client, auth_headers):
    response = await client.put(
        "/api/v1/users/me/llm-credential", json={"api_key": KEY}, headers=auth_headers
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["configured"] is True
    assert body["key_hint"] == f"{KEY[:5]}…{KEY[-4:]}"
    assert body["byok_enabled"] is True

    status = await client.get("/api/v1/users/me/llm-credential", headers=auth_headers)
    assert status.status_code == 200
    assert not PLAINTEXT_PATTERN.search(status.text)
    assert status.json()["configured"] is True

    deleted = await client.delete("/api/v1/users/me/llm-credential", headers=auth_headers)
    assert deleted.status_code == 204

    after = await client.get("/api/v1/users/me/llm-credential", headers=auth_headers)
    assert after.json()["configured"] is False


async def test_base_url_rejected_without_verify(client, auth_headers, monkeypatch):
    calls: list[str] = []

    async def _verify(api_key: str) -> bool:
        calls.append(api_key)
        return True

    monkeypatch.setattr(credential_service, "verify", _verify)
    response = await client.put(
        "/api/v1/users/me/llm-credential",
        json={"api_key": KEY, "base_url": "http://internal.evil.com"},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "LLM_CREDENTIAL_INVALID"
    assert calls == []


async def test_invalid_format_returns_400_not_422(client, auth_headers):
    response = await client.put(
        "/api/v1/users/me/llm-credential",
        json={"api_key": "not-a-key"},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "LLM_CREDENTIAL_INVALID"


async def test_verify_failure_returns_400_and_not_saved(client, auth_headers, monkeypatch):
    async def _fail(_api_key: str) -> bool:
        return False

    monkeypatch.setattr(credential_service, "verify", _fail)
    response = await client.put(
        "/api/v1/users/me/llm-credential", json={"api_key": KEY}, headers=auth_headers
    )
    assert response.status_code == 400

    status = await client.get("/api/v1/users/me/llm-credential", headers=auth_headers)
    assert status.json()["configured"] is False


async def test_trigger_endpoint_returns_428_without_key(client, auth_headers):
    response = await client.post(f"/api/v1/datasources/{uuid.uuid4()}/clean", headers=auth_headers)
    assert response.status_code == 428
    assert response.json()["error"]["code"] == "LLM_CREDENTIAL_NOT_CONFIGURED"


async def test_audit_written_without_secret(client, auth_headers, db_session, test_user):
    await client.put("/api/v1/users/me/llm-credential", json={"api_key": KEY}, headers=auth_headers)
    rows = (
        (await db_session.execute(select(AuditLog).where(AuditLog.user_id == test_user.id)))
        .scalars()
        .all()
    )
    actions = {row.action for row in rows}
    assert "credential_configured" in actions
    for row in rows:
        assert not PLAINTEXT_PATTERN.search(str(row.details or {}))


async def test_byok_disabled_hides_endpoints(client, auth_headers, monkeypatch):
    monkeypatch.setattr(settings, "BYOK_ENABLED", False)

    status = await client.get("/api/v1/users/me/llm-credential", headers=auth_headers)
    assert status.status_code == 200
    assert status.json()["byok_enabled"] is False

    put = await client.put(
        "/api/v1/users/me/llm-credential", json={"api_key": KEY}, headers=auth_headers
    )
    assert put.status_code == 404
