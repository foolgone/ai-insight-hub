"""媒体转写管线单测（application/media_pipeline）。

依赖通过参数注入，所以这里用 fake 对象即可，不需要 monkeypatch 具体实现模块。
"""
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


class _Transcriber:
    """满足 TranscriberPort 的假实现。"""

    def __init__(self, *, result: dict | None = None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.calls = 0
        self.progress_calls: list[str] = []

    async def transcribe_media(self, raw, asr, *, progress=None):  # noqa: ANN001, ANN201
        self.calls += 1
        if progress is not None:
            await progress("parsing asr 1/1")
            self.progress_calls.append("parsing asr 1/1")
        if self.error is not None:
            raise self.error
        return self.result or {}


async def _resolve_asr(_session, _user_id):  # noqa: ANN001, ANN202
    return object()


TRANSCRIPT = {
    "text": "你好",
    "media": {"channel_mode": "mono"},
    "asr": {"status": "completed", "model": "qwen3-asr-flash", "chunks": 1},
    "records": [{"dialogue_id": "asr-1", "user_message": "你好", "ai_response": ""}],
}


@pytest.mark.asyncio
async def test_reuses_completed_transcript() -> None:
    """已转写过的 raw 不再调用 ASR（重跑不重复计费）。"""
    transcriber = _Transcriber(result=TRANSCRIPT)
    raw = _Raw(
        {
            "format": "media",
            "asr": {"status": "completed"},
            "records": [{"dialogue_id": "asr-1"}],
        }
    )

    records, summary = await media_pipeline.prepare_media_records(
        raw,
        session=_Session(),
        user_id=uuid.uuid4(),
        transcriber=transcriber,
        resolve_asr=_resolve_asr,
    )

    assert records == [{"dialogue_id": "asr-1"}]
    assert summary is None
    assert transcriber.calls == 0


@pytest.mark.asyncio
async def test_transcribes_and_writes_back() -> None:
    transcriber = _Transcriber(result=TRANSCRIPT)
    raw = _Raw({"format": "media", "asr": {"status": "pending"}})
    session = _Session()
    steps: list[str] = []

    async def _report(step: str) -> None:
        steps.append(step)

    records, summary = await media_pipeline.prepare_media_records(
        raw,
        session=session,
        user_id=uuid.uuid4(),
        transcriber=transcriber,
        resolve_asr=_resolve_asr,
        on_progress=_report,
    )

    assert records == TRANSCRIPT["records"]
    assert summary == TRANSCRIPT["asr"]
    assert raw.raw_content["text"] == "你好"
    assert raw.raw_content["format"] == "media"  # 原有字段保留
    assert session.flushed == 1
    assert steps == ["parsing asr 1/1"]


@pytest.mark.asyncio
async def test_marks_raw_failed_without_owner() -> None:
    transcriber = _Transcriber(result=TRANSCRIPT)
    raw = _Raw({"format": "media", "asr": {"status": "pending"}})

    with pytest.raises(ValueError):
        await media_pipeline.prepare_media_records(
            raw,
            session=_Session(),
            user_id=None,
            transcriber=transcriber,
            resolve_asr=_resolve_asr,
        )

    assert raw.status == "failed"
    assert transcriber.calls == 0


@pytest.mark.asyncio
async def test_marks_raw_failed_when_asr_errors() -> None:
    transcriber = _Transcriber(error=RuntimeError("asr down"))
    raw = _Raw({"format": "media", "asr": {"status": "pending"}})

    with pytest.raises(RuntimeError):
        await media_pipeline.prepare_media_records(
            raw,
            session=_Session(),
            user_id=uuid.uuid4(),
            transcriber=transcriber,
            resolve_asr=_resolve_asr,
        )

    assert raw.status == "failed"
    assert transcriber.calls == 1
