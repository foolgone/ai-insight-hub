"""媒体转写管线单测（application/media_pipeline）。"""
from __future__ import annotations

import uuid

import pytest

from app.application import media_pipeline

pytestmark = pytest.mark.unit


class _Raw:
    def __init__(self, content: dict) -> None:
        self.raw_content = content
        self.status = "pending"


class _Session:
    def __init__(self) -> None:
        self.flushed = 0

    async def flush(self) -> None:
        self.flushed += 1


TRANSCRIPT = {
    "text": "你好",
    "media": {"channel_mode": "mono"},
    "asr": {"status": "completed", "model": "qwen3-asr-flash", "chunks": 1},
    "records": [{"dialogue_id": "asr-1", "user_message": "你好", "ai_response": ""}],
}


@pytest.mark.asyncio
async def test_reuses_completed_transcript(monkeypatch) -> None:
    """已转写过的 raw 不再调用 ASR（重跑不重复计费）。"""
    calls: list[str] = []

    async def _transcribe(*args, **kwargs):
        calls.append("transcribe")
        return TRANSCRIPT

    monkeypatch.setattr(media_pipeline.media_service, "transcribe_media", _transcribe)

    raw = _Raw(
        {
            "format": "media",
            "asr": {"status": "completed"},
            "records": [{"dialogue_id": "asr-1"}],
        }
    )
    records, summary = await media_pipeline.prepare_media_records(
        raw, session=_Session(), user_id=uuid.uuid4()
    )

    assert records == [{"dialogue_id": "asr-1"}]
    assert summary is None
    assert calls == []


@pytest.mark.asyncio
async def test_transcribes_and_writes_back(monkeypatch) -> None:
    async def _resolve(_session, _user_id):
        return object()

    async def _transcribe(_raw, _config, *, progress=None):
        if progress is not None:
            await progress("parsing asr 1/1")
        return TRANSCRIPT

    monkeypatch.setattr(media_pipeline.asr_service, "resolve_for_user", _resolve)
    monkeypatch.setattr(media_pipeline.media_service, "transcribe_media", _transcribe)

    raw = _Raw({"format": "media", "asr": {"status": "pending"}})
    session = _Session()
    steps: list[str] = []

    async def _report(step: str) -> None:
        steps.append(step)

    records, summary = await media_pipeline.prepare_media_records(
        raw, session=session, user_id=uuid.uuid4(), on_progress=_report
    )

    assert records == TRANSCRIPT["records"]
    assert summary == TRANSCRIPT["asr"]
    assert raw.raw_content["text"] == "你好"
    assert raw.raw_content["format"] == "media"  # 原有字段保留
    assert session.flushed == 1
    assert steps == ["parsing asr 1/1"]


@pytest.mark.asyncio
async def test_marks_raw_failed_without_owner(monkeypatch) -> None:
    raw = _Raw({"format": "media", "asr": {"status": "pending"}})

    with pytest.raises(ValueError):
        await media_pipeline.prepare_media_records(raw, session=_Session(), user_id=None)

    assert raw.status == "failed"


@pytest.mark.asyncio
async def test_marks_raw_failed_when_asr_errors(monkeypatch) -> None:
    async def _resolve(_session, _user_id):
        return object()

    async def _boom(*args, **kwargs):
        raise RuntimeError("asr down")

    monkeypatch.setattr(media_pipeline.asr_service, "resolve_for_user", _resolve)
    monkeypatch.setattr(media_pipeline.media_service, "transcribe_media", _boom)

    raw = _Raw({"format": "media", "asr": {"status": "pending"}})

    with pytest.raises(RuntimeError):
        await media_pipeline.prepare_media_records(raw, session=_Session(), user_id=uuid.uuid4())

    assert raw.status == "failed"
