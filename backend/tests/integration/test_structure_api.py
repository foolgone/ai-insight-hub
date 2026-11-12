"""转写与切分拆开后的接口测试：文件状态列表 + 重新切分入口。"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.composition import enqueue
from app.core.config import settings
from app.models import Task
from tests.factories import DataSourceFactory, RawDataFactory, persist

pytestmark = pytest.mark.integration


async def _media_raw(
    session,
    *,
    user,
    asr_status: str = "completed",
    structured: dict | None = None,
    format_: str = "media",
    structured_error: dict | None = None,
    datasource=None,
):
    if datasource is None:
        datasource = DataSourceFactory(user_id=user.id)
        await persist(session, datasource)
    content: dict = {
        "format": format_,
        "text": "面试官：请做一个自我介绍。" * 40,
        "media": {"channel_mode": "mono", "duration": 120.0, "channels": 1},
        "asr": {"status": asr_status},
        "records": [
            {
                "dialogue_id": "asr-1",
                "user_message": "整段转写",
                "ai_response": "",
                "speaker_pair": "mono",
                "issues": ["asr_transcript"],
            }
        ],
    }
    if structured is not None:
        content["structured"] = structured
    if structured_error is not None:
        content["structure_error"] = structured_error
    raw = RawDataFactory(
        datasource_id=datasource.id,
        raw_content=content,
        file_info={"filename": "interview.mp3", "size": 1024, "mime_type": "audio/mpeg"},
    )
    await persist(session, raw)
    return datasource, raw


async def test_list_raw_data_reports_transcribe_and_structure_state(
    client, auth_headers, db_session, test_user
) -> None:
    datasource, raw = await _media_raw(db_session, user=test_user)

    response = await client.get(
        f"/api/v1/datasources/{datasource.id}/raw-data", headers=auth_headers
    )

    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert len(items) == 1
    item = items[0]
    assert item["id"] == str(raw.id)
    assert item["filename"] == "interview.mp3"
    assert item["asr_status"] == "completed"
    assert item["structure_status"] == "pending"
    assert item["qa_count"] == 0
    assert item["duration"] == 120.0


async def test_list_raw_data_reports_done_and_failed(
    client, auth_headers, db_session, test_user
) -> None:
    datasource, done_raw = await _media_raw(
        db_session,
        user=test_user,
        structured={
            "structure": "qa",
            "content_type": "interview",
            "qa": [{"question": "q1", "answer": "a1"}, {"question": "q2", "answer": "a2"}],
        },
    )
    _, failed_raw = await _media_raw(
        db_session,
        user=test_user,
        datasource=datasource,
        structured_error={"message": "structure=summary but summary is empty", "chunks": 4},
    )

    response = await client.get(
        f"/api/v1/datasources/{datasource.id}/raw-data", headers=auth_headers
    )

    assert response.status_code == 200
    items = {item["id"]: item for item in response.json()["items"]}
    done = items[str(done_raw.id)]
    assert done["structure_status"] == "done"
    assert done["structure_kind"] == "qa"
    assert done["qa_count"] == 2
    failed = items[str(failed_raw.id)]
    assert failed["structure_status"] == "failed"
    assert "summary is empty" in failed["error"]


async def test_list_raw_data_reports_skipped_with_note(
    client, auth_headers, db_session, test_user
) -> None:
    """短音频 / 关闭结构化：不切分但保留整段文本，状态为 skipped 且带说明。"""
    datasource = DataSourceFactory(user_id=test_user.id)
    await persist(db_session, datasource)
    raw = RawDataFactory(
        datasource_id=datasource.id,
        raw_content={
            "format": "media",
            "text": "太短了。",
            "media": {"channel_mode": "mono", "duration": 5.0, "channels": 1},
            "asr": {"status": "completed"},
            "records": [{"dialogue_id": "asr-1", "speaker_pair": "mono"}],
            "structure_skipped": {"code": "text_too_short", "reason": "音频过短（转写文本低于结构化阈值），已保留整段文本"},
        },
        file_info={"filename": "short.mp3", "size": 10},
    )
    await persist(db_session, raw)

    response = await client.get(
        f"/api/v1/datasources/{datasource.id}/raw-data", headers=auth_headers
    )

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["structure_status"] == "skipped"
    assert "已保留整段文本" in item["note"]
    assert item["structure_kind"] is None


async def test_structure_endpoint_queues_task(
    client, auth_headers, db_session, test_user, monkeypatch
) -> None:
    datasource, raw = await _media_raw(db_session, user=test_user)
    monkeypatch.setattr(settings, "ALLOW_SERVER_KEY_FALLBACK", True)
    monkeypatch.setattr(enqueue, "enqueue_structure", lambda task_id: "celery-structure-1")

    response = await client.post(
        f"/api/v1/datasources/{datasource.id}/raw-data/{raw.id}/structure",
        headers=auth_headers,
    )

    assert response.status_code == 202, response.text
    payload = response.json()
    task = await db_session.get(Task, uuid.UUID(payload["task_id"]))
    assert task is not None
    assert task.task_type == "structure"
    assert task.params["raw_data_id"] == str(raw.id)
    assert task.celery_task_id == "celery-structure-1"


async def test_structure_endpoint_rejects_untranscribed_raw(
    client, auth_headers, db_session, test_user, monkeypatch
) -> None:
    datasource, raw = await _media_raw(db_session, user=test_user, asr_status="pending")
    monkeypatch.setattr(settings, "ALLOW_SERVER_KEY_FALLBACK", True)

    response = await client.post(
        f"/api/v1/datasources/{datasource.id}/raw-data/{raw.id}/structure",
        headers=auth_headers,
    )

    assert response.status_code == 409
    assert "尚未完成转写" in response.json()["error"]["message"]


async def test_structure_endpoint_rejects_text_raw(
    client, auth_headers, db_session, test_user, monkeypatch
) -> None:
    datasource, raw = await _media_raw(db_session, user=test_user, format_="csv")
    monkeypatch.setattr(settings, "ALLOW_SERVER_KEY_FALLBACK", True)

    response = await client.post(
        f"/api/v1/datasources/{datasource.id}/raw-data/{raw.id}/structure",
        headers=auth_headers,
    )

    assert response.status_code == 409
    assert "只有音视频" in response.json()["error"]["message"]


async def test_structure_endpoint_404_for_other_datasource(
    client, auth_headers, db_session, test_user, monkeypatch
) -> None:
    datasource, _ = await _media_raw(db_session, user=test_user)
    _, foreign_raw = await _media_raw(db_session, user=test_user)
    monkeypatch.setattr(settings, "ALLOW_SERVER_KEY_FALLBACK", True)

    response = await client.post(
        f"/api/v1/datasources/{datasource.id}/raw-data/{foreign_raw.id}/structure",
        headers=auth_headers,
    )

    assert response.status_code == 404


async def test_structure_running_task_is_rejected(
    client, auth_headers, db_session, test_user, monkeypatch
) -> None:
    datasource, raw = await _media_raw(db_session, user=test_user)
    monkeypatch.setattr(settings, "ALLOW_SERVER_KEY_FALLBACK", True)
    monkeypatch.setattr(enqueue, "enqueue_structure", lambda task_id: "celery-1")

    first = await client.post(
        f"/api/v1/datasources/{datasource.id}/raw-data/{raw.id}/structure",
        headers=auth_headers,
    )
    assert first.status_code == 202

    second = await client.post(
        f"/api/v1/datasources/{datasource.id}/raw-data/{raw.id}/structure",
        headers=auth_headers,
    )
    assert second.status_code == 409

    rows = (
        (
            await db_session.execute(
                select(Task).where(
                    Task.task_type == "structure", Task.params["raw_data_id"].astext == str(raw.id)
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
