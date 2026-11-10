"""媒体上传分支集成测试（不调用真实 ASR/ffmpeg）。"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.composition import enqueue
from app.core.config import settings
from app.models import RawData
from app.services.credential_service import credential_service

pytestmark = pytest.mark.integration


class _ActiveRow:
    status = "active"


async def _active_any(_session, _user_id, _provider="deepseek"):
    return _ActiveRow()


async def _only_llm(_session, _user_id, _provider="deepseek"):
    return _ActiveRow() if _provider == "deepseek" else None


async def _datasource(client, auth_headers) -> str:
    response = await client.post(
        "/api/v1/datasources",
        headers=auth_headers,
        json={"name": "media-upload-ds", "type": "customer_service"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def test_upload_media_creates_media_raw_data(
    client, auth_headers, db_session, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "ASR_ENABLED", True)
    monkeypatch.setattr(credential_service, "get_credential", _active_any)
    monkeypatch.setattr(enqueue, "enqueue_clean", lambda task_id: "celery-media-1")
    datasource_id = await _datasource(client, auth_headers)

    response = await client.post(
        f"/api/v1/datasources/{datasource_id}/upload",
        headers=auth_headers,
        files={"file": ("call.mp3", b"ID3-fake-audio", "audio/mpeg")},
    )

    assert response.status_code == 202, response.text
    assert response.json()["task_id"]

    raw = (
        await db_session.execute(select(RawData).where(RawData.datasource_id == datasource_id))
    ).scalar_one()
    assert raw.raw_content["format"] == "media"
    assert raw.raw_content["asr"]["status"] == "pending"
    assert raw.file_info["object_name"]
    assert raw.file_info["filename"] == "call.mp3"


async def test_upload_media_rejected_when_asr_disabled(client, auth_headers, monkeypatch) -> None:
    monkeypatch.setattr(settings, "ASR_ENABLED", False)
    monkeypatch.setattr(credential_service, "get_credential", _active_any)
    datasource_id = await _datasource(client, auth_headers)

    response = await client.post(
        f"/api/v1/datasources/{datasource_id}/upload",
        headers=auth_headers,
        files={"file": ("call.mp3", b"ID3-fake-audio", "audio/mpeg")},
    )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "FILE_FORMAT_INVALID"
    assert response.json()["error"]["details"]["reason"] == "asr_disabled"


async def test_upload_media_requires_asr_credential(client, auth_headers, monkeypatch) -> None:
    """有 LLM Key 但没有语音转写配置 → 428，引导去前端配置。"""
    monkeypatch.setattr(settings, "ASR_ENABLED", True)
    monkeypatch.setattr(credential_service, "get_credential", _only_llm)
    datasource_id = await _datasource(client, auth_headers)

    response = await client.post(
        f"/api/v1/datasources/{datasource_id}/upload",
        headers=auth_headers,
        files={"file": ("call.mp3", b"ID3-fake-audio", "audio/mpeg")},
    )

    assert response.status_code == 428
    assert response.json()["error"]["code"] == "ASR_CREDENTIAL_NOT_CONFIGURED"


async def test_upload_text_unaffected_by_asr_config(
    client, auth_headers, db_session, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "ASR_ENABLED", True)
    monkeypatch.setattr(credential_service, "get_credential", _only_llm)
    monkeypatch.setattr(enqueue, "enqueue_clean", lambda task_id: "celery-text-1")
    datasource_id = await _datasource(client, auth_headers)

    response = await client.post(
        f"/api/v1/datasources/{datasource_id}/upload",
        headers=auth_headers,
        files={"file": ("dialogues.txt", "客户：在吗\n客服：在的".encode(), "text/plain")},
    )

    assert response.status_code == 202, response.text
    raw = (
        await db_session.execute(select(RawData).where(RawData.datasource_id == datasource_id))
    ).scalar_one()
    assert raw.raw_content["format"] != "media"
