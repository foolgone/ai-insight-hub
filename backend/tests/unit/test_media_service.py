"""音视频转写服务单测（不依赖 ffmpeg / 真实 ASR）。"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from app.core.config import settings
from app.services import media_service
from app.services.media_service import AsrResult, AsrSegment

pytestmark = pytest.mark.unit


def test_pair_dialogues_lr() -> None:
    left = [
        AsrSegment(start=0.0, end=2.0, text="我的订单怎么还没发货？", speaker="L"),
        AsrSegment(start=10.0, end=12.0, text="还有别的办法吗？", speaker="L"),
    ]
    right = [
        AsrSegment(start=3.0, end=5.0, text="您好，我帮您查一下。", speaker="R"),
        AsrSegment(start=13.0, end=14.0, text="可以申请补偿。", speaker="R"),
    ]

    records = media_service._pair_dialogues(
        left, right, anchor=datetime(2026, 11, 8, 10, 0, 0)
    )

    assert len(records) == 2
    assert records[0]["user_message"] == "我的订单怎么还没发货？"
    assert records[0]["ai_response"] == "您好，我帮您查一下。"
    assert records[0]["source"] == "asr"
    assert records[0]["speaker_pair"] == "L/R"
    assert records[0]["quality_score"] is None
    assert "asr_transcript" in records[0]["issues"]
    assert records[0]["timestamp"] == "2026-11-08T10:00:00"
    assert records[1]["user_message"] == "还有别的办法吗？"


def test_pair_dialogues_agent_starts_first() -> None:
    left = [AsrSegment(start=5.0, end=6.0, text="嗯嗯", speaker="L")]
    right = [
        AsrSegment(start=0.0, end=2.0, text="您好，请问有什么可以帮您？", speaker="R"),
        AsrSegment(start=7.0, end=8.0, text="好的。", speaker="R"),
    ]

    records = media_service._pair_dialogues(
        left, right, anchor=datetime(2026, 11, 8, 10, 0, 0)
    )

    assert len(records) == 1
    assert records[0]["user_message"] == "嗯嗯"
    assert "您好" in records[0]["ai_response"]
    assert "好的" in records[0]["ai_response"]


def test_pair_dialogues_empty() -> None:
    assert media_service._pair_dialogues([], [], anchor=datetime(2026, 11, 8)) == []


def test_mono_records() -> None:
    result = AsrResult(
        text="客户：我想退货。客服：好的。",
        segments=[],
        language="zh",
        duration=3.0,
        cost_estimate=0.0,
    )

    records = media_service._mono_records(result, anchor=datetime(2026, 11, 8, 10, 0, 0))

    assert len(records) == 1
    assert records[0]["speaker_pair"] == "mono"
    assert records[0]["ai_response"] == ""
    assert "mono_speaker_unknown" in records[0]["issues"]


@pytest.mark.asyncio
async def test_transcribe_track_merges_segments(monkeypatch) -> None:
    async def fake_chunk(path: Path, seconds: int):
        return [(path, 0.0)]

    async def fake_transcribe(path: Path, *, offset: float = 0.0):
        return AsrResult(
            text="hello",
            segments=[AsrSegment(start=0.0 + offset, end=1.0 + offset, text="hello")],
            language="zh",
            duration=1.0,
            cost_estimate=0.0,
        )

    monkeypatch.setattr(media_service, "chunk_audio", fake_chunk)
    monkeypatch.setattr(media_service, "_transcribe_file", fake_transcribe)

    result, chunks = await media_service._transcribe_track(
        Path("left.mp3"), speaker="L", progress=None
    )

    assert chunks == 1
    assert result.segments[0].speaker == "L"
    assert result.text == "hello"


@pytest.mark.asyncio
async def test_transcribe_file_requires_configuration() -> None:
    monkeypatch_off = settings.ASR_ENABLED
    settings.ASR_ENABLED = False
    try:
        with pytest.raises(media_service.AsrNotConfiguredError):
            await media_service._transcribe_file(Path("missing.mp3"))
    finally:
        settings.ASR_ENABLED = monkeypatch_off


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.text = "error"

    def json(self):
        return self._payload


class _FakeClient:
    responses: list[_FakeResponse] = []
    calls: int = 0

    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def post(self, *args, **kwargs):
        _FakeClient.calls += 1
        return _FakeClient.responses.pop(0)


@pytest.mark.asyncio
async def test_transcribe_file_parses_segments(tmp_path: Path, monkeypatch) -> None:
    audio = tmp_path / "a.mp3"
    audio.write_bytes(b"fake")
    _FakeClient.calls = 0
    _FakeClient.responses = [
        _FakeResponse(
            200,
            {
                "text": "你好 世界",
                "language": "zh",
                "duration": 2.0,
                "segments": [
                    {"start": 0.0, "end": 1.0, "text": "你好"},
                    {"start": 1.0, "end": 2.0, "text": "世界"},
                ],
            },
        )
    ]
    monkeypatch.setattr(media_service.httpx, "AsyncClient", _FakeClient)
    monkeypatch.setattr(settings, "ASR_ENABLED", True)
    monkeypatch.setattr(settings, "ASR_API_KEY", "test-key")

    result = await media_service._transcribe_file(audio, offset=10.0)

    assert result.text == "你好 世界"
    assert result.segments[0].start == 10.0
    assert result.segments[1].end == 12.0
    assert _FakeClient.calls == 1


@pytest.mark.asyncio
async def test_transcribe_file_does_not_retry_4xx(tmp_path: Path, monkeypatch) -> None:
    audio = tmp_path / "a.mp3"
    audio.write_bytes(b"fake")
    _FakeClient.calls = 0
    _FakeClient.responses = [_FakeResponse(401), _FakeResponse(200, {"segments": []})]
    monkeypatch.setattr(media_service.httpx, "AsyncClient", _FakeClient)
    monkeypatch.setattr(settings, "ASR_ENABLED", True)
    monkeypatch.setattr(settings, "ASR_API_KEY", "bad-key")

    with pytest.raises(media_service.AsrRequestError):
        await media_service._transcribe_file(audio)

    assert _FakeClient.calls == 1

