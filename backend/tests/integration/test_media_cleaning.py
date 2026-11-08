"""音视频媒体清洗分支集成测试（mock ASR，不依赖 ffmpeg/外部服务）。"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models import CleanedData
from app.services import asr_service, cleaning_service, media_service
from tests.factories import (
    DataSourceFactory,
    RawDataFactory,
    TaskFactory,
    UserFactory,
    persist,
)

pytestmark = pytest.mark.integration

ASR_CONFIG = asr_service.AsrConfig(
    base_url="https://asr.example.com/v1",
    api_key="test-key-1234",
    model="whisper-1",
    language="zh",
)


async def _fake_resolve(_session, _user_id):
    return ASR_CONFIG


RECORDS = [
    {
        "dialogue_id": "asr-1",
        "timestamp": "2026-11-08T10:00:01",
        "user_message": "我的订单怎么还没发货？",
        "ai_response": "您好，我帮您查一下。",
        "quality_score": None,
        "issues": ["asr_transcript"],
        "source": "asr",
        "speaker_pair": "L/R",
    },
    {
        "dialogue_id": "asr-2",
        "timestamp": "2026-11-08T10:00:10",
        "user_message": "那什么时候能到？",
        "ai_response": "预计今天发出。",
        "quality_score": None,
        "issues": ["asr_transcript"],
        "source": "asr",
        "speaker_pair": "L/R",
    },
]

TRANSCRIPT = {
    "text": "我的订单怎么还没发货？ 您好，我帮您查一下。 那什么时候能到？ 预计今天发出。",
    "media": {"filename": "call.mp4", "duration": 20.0, "channels": 2, "sample_rate": 16000},
    "asr": {
        "provider": "openai_compatible",
        "model": "whisper-1",
        "language": "zh",
        "status": "completed",
        "chunks": 1,
        "duration": 20.0,
        "cost_estimate": 0.002,
        "finished_at": "2026-11-08T10:00:20",
        "error": None,
    },
    "records": RECORDS,
}


async def _setup(db_session) -> tuple:
    user = UserFactory()
    await persist(db_session, user)
    datasource = DataSourceFactory(user_id=user.id)
    await persist(db_session, datasource)
    raw = RawDataFactory(
        datasource_id=datasource.id,
        raw_content={
            "format": "media",
            "media": {"filename": "call.mp4", "size": 1024},
            "asr": {"status": "pending"},
        },
        file_info={"filename": "call.mp4", "object_name": "fake/call.mp4"},
    )
    await persist(db_session, raw)
    task = TaskFactory(
        user_id=user.id,
        datasource_id=datasource.id,
        task_type="clean",
        status="pending",
        params={"raw_data_id": str(raw.id)},
    )
    await persist(db_session, task)
    return datasource, raw, task


async def test_media_clean_writes_dialogues(db_session, monkeypatch) -> None:
    datasource, raw, task = await _setup(db_session)
    calls: list[str] = []

    async def fake_transcribe(raw_data, config, *, progress=None):
        assert config == ASR_CONFIG
        calls.append(str(raw_data.id))
        if progress is not None:
            await progress("parsing asr 1/1")
        return TRANSCRIPT

    monkeypatch.setattr(media_service, "transcribe_media", fake_transcribe)
    monkeypatch.setattr(asr_service, "resolve_for_user", _fake_resolve)

    outcome = await cleaning_service.run_clean_task(str(task.id), session=db_session)

    assert outcome["status"] == "completed"
    assert outcome["cleaned_records"] == 2
    assert calls == [str(raw.id)]

    rows = (
        (
            await db_session.execute(
                select(CleanedData).where(CleanedData.datasource_id == datasource.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 2
    assert rows[0].metadata_["source"] == "asr"
    assert rows[0].metadata_["speaker_pair"] == "L/R"
    assert rows[0].quality_score is None

    await db_session.refresh(raw)
    assert raw.raw_content["asr"]["status"] == "completed"
    assert raw.raw_content["records"][0]["source"] == "asr"

    await db_session.refresh(task)
    assert task.result["asr"]["status"] == "completed"
    assert task.result["asr"]["chunks"] == 1


async def test_media_clean_skips_asr_on_rerun(db_session, monkeypatch) -> None:
    _, _, task = await _setup(db_session)
    calls: list[str] = []

    async def fake_transcribe(raw_data, config, *, progress=None):
        calls.append(str(raw_data.id))
        return TRANSCRIPT

    monkeypatch.setattr(media_service, "transcribe_media", fake_transcribe)
    monkeypatch.setattr(asr_service, "resolve_for_user", _fake_resolve)

    first = await cleaning_service.run_clean_task(str(task.id), session=db_session)
    second = await cleaning_service.run_clean_task(str(task.id), session=db_session)

    assert first["status"] == "completed"
    assert second["status"] == "completed"
    assert len(calls) == 1
    assert second["cleaned_records"] == 0


async def test_media_clean_failure_marks_raw_failed(db_session, monkeypatch) -> None:
    _, raw, task = await _setup(db_session)

    async def fake_transcribe(raw_data, config, *, progress=None):
        raise media_service.MediaDecodeError("ffmpeg failed")

    monkeypatch.setattr(media_service, "transcribe_media", fake_transcribe)
    monkeypatch.setattr(asr_service, "resolve_for_user", _fake_resolve)

    outcome = await cleaning_service.run_clean_task(str(task.id), session=db_session)

    assert outcome["status"] == "failed"
    await db_session.refresh(raw)
    assert raw.status == "failed"
    await db_session.refresh(task)
    assert task.status == "failed"
    assert "ffmpeg failed" in (task.error_message or "")


async def test_media_clean_fails_when_asr_not_configured(db_session, monkeypatch) -> None:
    """未配置 ASR 时不静默跳过，任务失败且原因可读。"""
    _, raw, task = await _setup(db_session)

    async def _no_config(_session, _user_id):
        raise asr_service.AsrCredentialNotConfiguredError()

    monkeypatch.setattr(asr_service, "resolve_for_user", _no_config)

    outcome = await cleaning_service.run_clean_task(str(task.id), session=db_session)

    assert outcome["status"] == "failed"
    await db_session.refresh(raw)
    assert raw.status == "failed"
    await db_session.refresh(task)
    assert "语音转写" in (task.error_message or "")
