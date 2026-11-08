"""语音转写配置 API 集成测试（BYOK 扩展）。

覆盖：保存/查询/删除、地址安全校验、连通性校验失败不入库、
与 LLM Key 共存（同一张表不同 provider）、开关矩阵。
"""
from __future__ import annotations

import re

import pytest
from cryptography.fernet import Fernet

from app.api.v1 import asr_credential as asr_credential_api
from app.core.config import settings

pytestmark = pytest.mark.integration

KEY = "asr-key-0000000000"
PLAINTEXT_PATTERN = re.compile(r"asr-key-[0-9]{6,}")
BASE_URL = "https://asr.example.com/v1"


@pytest.fixture(autouse=True)
def asr_env(monkeypatch):
    monkeypatch.setattr(settings, "ASR_ENABLED", True)
    monkeypatch.setattr(settings, "CREDENTIAL_ENCRYPTION_KEY", Fernet.generate_key().decode())
    # 测试不走真实 DNS：把测试域名放进白名单
    monkeypatch.setattr(settings, "ASR_ALLOWED_HOSTS", "asr.example.com")
    monkeypatch.setattr(settings, "ASR_ALLOW_HTTP", False)


@pytest.fixture(autouse=True)
def no_real_verify(monkeypatch):
    async def _ok(_config):
        return True, None

    monkeypatch.setattr(asr_credential_api, "verify_config", _ok)


async def _save(client, auth_headers, **overrides):
    payload = {
        "base_url": BASE_URL,
        "api_key": KEY,
        "model": "whisper-1",
        "language": "zh",
    }
    payload.update(overrides)
    return await client.put(
        "/api/v1/users/me/asr-credential", json=payload, headers=auth_headers
    )


async def test_put_get_delete_roundtrip(client, auth_headers):
    response = await _save(client, auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["configured"] is True
    assert body["base_url"] == BASE_URL
    assert body["model"] == "whisper-1"
    assert body["key_hint"] == f"{KEY[:5]}…{KEY[-4:]}"
    assert body["asr_enabled"] is True

    status = await client.get("/api/v1/users/me/asr-credential", headers=auth_headers)
    assert status.status_code == 200
    assert status.json()["configured"] is True
    assert not PLAINTEXT_PATTERN.search(status.text)

    deleted = await client.delete("/api/v1/users/me/asr-credential", headers=auth_headers)
    assert deleted.status_code == 204

    after = await client.get("/api/v1/users/me/asr-credential", headers=auth_headers)
    assert after.json()["configured"] is False


async def test_private_address_rejected(client, auth_headers, monkeypatch):
    calls: list = []

    async def _verify(config):
        calls.append(config)
        return True, None

    monkeypatch.setattr(asr_credential_api, "verify_config", _verify)

    response = await _save(client, auth_headers, base_url="https://127.0.0.1:8443/v1")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "ASR_CREDENTIAL_INVALID"
    assert calls == []


async def test_http_rejected_by_default(client, auth_headers):
    response = await _save(client, auth_headers, base_url="http://asr.example.com/v1")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "ASR_CREDENTIAL_INVALID"


async def test_missing_model_rejected(client, auth_headers):
    response = await _save(client, auth_headers, model="  ")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "ASR_CREDENTIAL_INVALID"


async def test_verify_failure_returns_400_and_not_saved(client, auth_headers, monkeypatch):
    async def _fail(_config):
        return False, "API Key 无效或无权限"

    monkeypatch.setattr(asr_credential_api, "verify_config", _fail)

    response = await _save(client, auth_headers)
    assert response.status_code == 400
    assert "API Key 无效" in response.json()["error"]["message"]

    status = await client.get("/api/v1/users/me/asr-credential", headers=auth_headers)
    assert status.json()["configured"] is False


async def test_llm_and_asr_credentials_coexist(client, auth_headers, monkeypatch):
    from app.services.credential_service import credential_service

    async def _ok_llm(_api_key: str) -> bool:
        return True

    monkeypatch.setattr(credential_service, "verify", _ok_llm)

    llm = await client.put(
        "/api/v1/users/me/llm-credential",
        json={"api_key": "sk-userkey0000000000"},
        headers=auth_headers,
    )
    assert llm.status_code == 200, llm.text

    asr = await _save(client, auth_headers)
    assert asr.status_code == 200, asr.text

    llm_status = await client.get("/api/v1/users/me/llm-credential", headers=auth_headers)
    asr_status = await client.get("/api/v1/users/me/asr-credential", headers=auth_headers)
    assert llm_status.json()["configured"] is True
    assert asr_status.json()["configured"] is True


async def test_asr_disabled_hides_endpoints(client, auth_headers, monkeypatch):
    monkeypatch.setattr(settings, "ASR_ENABLED", False)

    status = await client.get("/api/v1/users/me/asr-credential", headers=auth_headers)
    assert status.status_code == 200
    assert status.json()["asr_enabled"] is False

    put = await _save(client, auth_headers)
    assert put.status_code == 404
