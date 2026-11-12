"""内容结构化与分流单测（application/structure_service）。"""
from __future__ import annotations

import uuid

import pytest

from app.agents.base import AgentResult
from app.application import structure_service
from app.core.config import settings
from app.services import cleaning_service

pytestmark = pytest.mark.unit


class _Raw:
    def __init__(self, content: dict) -> None:
        self.id = uuid.uuid4()
        self.raw_content = content
        self.status = "pending"


class _Session:
    def __init__(self) -> None:
        self.added: list[object] = []

    def add(self, obj: object) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        return None


class _FakeAgent:
    def __init__(self, data: dict) -> None:
        self._data = data

    async def structure(self, input_data, **kwargs) -> AgentResult:
        return AgentResult(
            success=True,
            data=dict(self._data),
            metadata={"agent": "structure_agent", "version": "v1.0.0", "model": "fake"},
            duration=1.0,
            token_usage={"input": 100, "output": 50},
        )


MONO_RECORD = [{"dialogue_id": "asr-1", "user_message": "整段文本", "speaker_pair": "mono"}]
LONG_TEXT = "面试官：请你做一个自我介绍。候选人：" + "我做过后端开发。" * 30

QA_PAYLOAD = {
    "content_type": "interview",
    "structure": "qa",
    "confidence": 0.9,
    "qa": [
        {"question": "请你做一个自我介绍。", "answer": "我做过后端开发。", "quality_score": 82},
        {"question": "你做过什么项目？", "answer": "一个综合执法平台。", "quality_score": 120},
    ],
}

KNOWLEDGE_PAYLOAD = {
    "content_type": "monologue",
    "structure": "knowledge",
    "confidence": 0.7,
    "knowledge": [
        {"title": "索引失效排查", "content": "先看执行计划", "tags": ["数据库", "SQL"]},
    ],
}

SUMMARY_PAYLOAD = {
    "content_type": "meeting",
    "structure": "summary",
    "confidence": 0.8,
    "summary": "讨论了三个议题，结论是先做 P1。",
}


def _media_content(text: str = LONG_TEXT) -> dict:
    return {
        "format": "media",
        "text": text,
        "media": {"channel_mode": "dual_mono", "duration": 100.0},
        "asr": {"status": "completed"},
        "records": MONO_RECORD,
    }


def test_qa_to_dialogues_maps_and_clamps() -> None:
    dialogues = structure_service.qa_to_dialogues(QA_PAYLOAD)

    assert len(dialogues) == 2
    first = dialogues[0]
    assert first["user_message"] == "请你做一个自我介绍。"
    assert first["ai_response"] == "我做过后端开发。"
    assert first["quality_score"] == 82
    assert first["source"] == "asr_structured"
    assert first["speaker_pair"] == "inferred"
    assert "speaker_inferred" in first["issues"]
    # 超出 0-100 的分数被截断
    assert dialogues[1]["quality_score"] == 100.0


def test_qa_to_dialogues_skips_empty_items() -> None:
    payload = {"qa": [{"question": "", "answer": ""}, {"question": "q", "answer": "a"}]}
    dialogues = structure_service.qa_to_dialogues(payload)
    assert len(dialogues) == 1
    assert dialogues[0]["dialogue_id"] == "qa-2"


@pytest.mark.asyncio
async def test_apply_skips_when_disabled(monkeypatch) -> None:
    monkeypatch.setattr(settings, "MEDIA_STRUCTURE_ENABLED", False)
    raw = _Raw(_media_content())
    result = await structure_service.apply(
        _Session(),
        raw=raw,
        records=MONO_RECORD,
        task_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        datasource_id=uuid.uuid4(),
    )
    assert result is None
    assert "structured" not in raw.raw_content


@pytest.mark.asyncio
async def test_apply_skips_stereo_records(monkeypatch) -> None:
    monkeypatch.setattr(settings, "MEDIA_STRUCTURE_ENABLED", True)
    raw = _Raw(_media_content())
    stereo = [{"speaker_pair": "L/R"}, {"speaker_pair": "L/R"}]
    result = await structure_service.apply(
        _Session(),
        raw=raw,
        records=stereo,
        task_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        datasource_id=uuid.uuid4(),
    )
    assert result is None


@pytest.mark.asyncio
async def test_apply_skips_short_text(monkeypatch) -> None:
    monkeypatch.setattr(settings, "MEDIA_STRUCTURE_ENABLED", True)
    monkeypatch.setattr(settings, "MEDIA_STRUCTURE_MIN_CHARS", 200)
    raw = _Raw(_media_content("太短了"))
    result = await structure_service.apply(
        _Session(),
        raw=raw,
        records=MONO_RECORD,
        task_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        datasource_id=uuid.uuid4(),
    )
    assert result is None


@pytest.mark.asyncio
async def test_apply_qa_writes_structured(monkeypatch) -> None:
    monkeypatch.setattr(settings, "MEDIA_STRUCTURE_ENABLED", True)
    monkeypatch.setattr(structure_service, "_build_agent", lambda *_: _FakeAgent(QA_PAYLOAD))

    raw = _Raw(_media_content())
    result = await structure_service.apply(
        _Session(),
        raw=raw,
        records=MONO_RECORD,
        task_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        datasource_id=uuid.uuid4(),
    )

    assert result is not None
    assert result["structure"] == "qa"
    assert result["schema_version"] == 1
    assert raw.raw_content["structured"]["structure"] == "qa"


@pytest.mark.asyncio
async def test_apply_reuses_existing_structured(monkeypatch) -> None:
    monkeypatch.setattr(settings, "MEDIA_STRUCTURE_ENABLED", True)

    def _boom(*_args, **_kwargs):
        raise AssertionError("should not call agent")

    monkeypatch.setattr(structure_service, "_build_agent", _boom)

    raw = _Raw({**_media_content(), "structured": {"structure": "summary", "summary": "x"}})
    result = await structure_service.apply(
        _Session(),
        raw=raw,
        records=MONO_RECORD,
        task_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        datasource_id=uuid.uuid4(),
    )
    assert result == {"structure": "summary", "summary": "x"}


@pytest.mark.asyncio
async def test_apply_knowledge_persists_rows(monkeypatch) -> None:
    monkeypatch.setattr(settings, "MEDIA_STRUCTURE_ENABLED", True)
    monkeypatch.setattr(structure_service, "_build_agent", lambda *_: _FakeAgent(KNOWLEDGE_PAYLOAD))

    session = _Session()
    raw = _Raw(_media_content())
    result = await structure_service.apply(
        session,
        raw=raw,
        records=MONO_RECORD,
        task_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        datasource_id=uuid.uuid4(),
    )

    assert result["structure"] == "knowledge"
    assert len(session.added) == 1
    row = session.added[0]
    assert row.question == "索引失效排查"
    assert row.source == "extracted"
    assert row.status == "needs_review"
    assert row.tags == ["数据库", "SQL"]


@pytest.mark.asyncio
async def test_apply_summary_persists_analysis(monkeypatch) -> None:
    monkeypatch.setattr(settings, "MEDIA_STRUCTURE_ENABLED", True)
    monkeypatch.setattr(structure_service, "_build_agent", lambda *_: _FakeAgent(SUMMARY_PAYLOAD))

    session = _Session()
    raw = _Raw(_media_content())
    result = await structure_service.apply(
        session,
        raw=raw,
        records=MONO_RECORD,
        task_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        datasource_id=uuid.uuid4(),
    )

    assert result["structure"] == "summary"
    assert len(session.added) == 1
    row = session.added[0]
    assert row.analysis_type == "other"
    assert row.result["kind"] == "transcript_summary"
    assert row.result["summary"].startswith("讨论了三个议题")


# --------------------------------------------------------------------------- 分块 / 部分失败


class _SeqAgent:
    """按调用顺序返回预设结果：dict 表示成功，`{"__fail__": msg}` 表示失败。"""

    def __init__(self, results: list[dict]) -> None:
        self._results = list(results)
        self.calls = 0

    async def structure(self, input_data, **kwargs) -> AgentResult:
        self.calls += 1
        item = self._results.pop(0) if self._results else {"__fail__": "no more results"}
        if "__fail__" in item:
            return AgentResult(
                success=False,
                data=None,
                errors=[f"AgentOutputError: {item['__fail__']}"],
                duration=1.0,
                token_usage={"input": 10, "output": 0},
            )
        return AgentResult(
            success=True,
            data=dict(item),
            metadata={"agent": "structure_agent", "version": "v1.0.0", "model": "fake"},
            duration=1.0,
            token_usage={"input": 100, "output": 50},
        )


def _qa_payload(question: str) -> dict:
    return {
        "content_type": "interview",
        "structure": "qa",
        "confidence": 0.9,
        "qa": [{"question": question, "answer": f"{question} 的回答", "quality_score": 80}],
    }


def _chunked_text() -> str:
    # 400 句 × 17 字 ≈ 6800 字，确保被切成多块
    return "面试官：请介绍一下你的项目经历。" * 400


@pytest.mark.asyncio
async def test_apply_splits_long_transcript_and_merges(monkeypatch) -> None:
    monkeypatch.setattr(settings, "MEDIA_STRUCTURE_ENABLED", True)
    text = _chunked_text()
    expected_chunks = len(structure_service.split_transcript(text))
    assert expected_chunks > 1

    agent = _SeqAgent([_qa_payload(f"第{i}问") for i in range(expected_chunks)])
    monkeypatch.setattr(structure_service, "_build_agent", lambda *_: agent)
    raw = _Raw(_media_content(text))
    result = await structure_service.apply(
        _Session(),
        raw=raw,
        records=MONO_RECORD,
        task_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        datasource_id=uuid.uuid4(),
    )

    assert agent.calls == expected_chunks
    assert result["structure"] == "qa"
    assert len(result["qa"]) == expected_chunks  # 每块的问答都保留
    assert result["merge"]["chunks_total"] == expected_chunks
    assert not result.get("partial")
    assert raw.raw_content["structured"]["structure"] == "qa"


@pytest.mark.asyncio
async def test_apply_partial_failure_keeps_successful_chunks(monkeypatch) -> None:
    monkeypatch.setattr(settings, "MEDIA_STRUCTURE_ENABLED", True)
    text = _chunked_text()
    expected_chunks = len(structure_service.split_transcript(text))
    assert expected_chunks >= 3

    failure = {"__fail__": "structure=summary but summary is empty"}
    results: list[dict] = []
    for index in range(expected_chunks):
        results.append(failure if index == 1 else _qa_payload(f"第{index}问"))
    agent = _SeqAgent(results)
    monkeypatch.setattr(structure_service, "_build_agent", lambda *_: agent)

    raw = _Raw(_media_content(text))
    result = await structure_service.apply(
        _Session(),
        raw=raw,
        records=MONO_RECORD,
        task_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        datasource_id=uuid.uuid4(),
    )

    assert result["structure"] == "qa"
    assert result["partial"] is True
    assert len(result["failed_chunks"]) == 1
    assert len(result["qa"]) == expected_chunks - 1


@pytest.mark.asyncio
async def test_apply_total_failure_writes_structure_error(monkeypatch) -> None:
    monkeypatch.setattr(settings, "MEDIA_STRUCTURE_ENABLED", True)
    text = _chunked_text()
    expected_chunks = len(structure_service.split_transcript(text))
    results = [
        {"__fail__": "structure=summary but summary is empty"} for _ in range(expected_chunks)
    ]
    agent = _SeqAgent(results)
    monkeypatch.setattr(structure_service, "_build_agent", lambda *_: agent)

    raw = _Raw(_media_content(text))
    result = await structure_service.apply(
        _Session(),
        raw=raw,
        records=MONO_RECORD,
        task_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        datasource_id=uuid.uuid4(),
    )

    assert result is None
    assert "structured" not in raw.raw_content
    error = raw.raw_content["structure_error"]
    assert "summary is empty" in error["message"]
    assert error["chunks"] == expected_chunks


def test_mark_structure_unparsed_adds_issue_once() -> None:
    records = [{"issues": ["asr_transcript"]}, {"issues": []}]
    cleaning_service._mark_structure_unparsed(records)  # noqa: SLF001
    cleaning_service._mark_structure_unparsed(records)  # noqa: SLF001 - 幂等

    assert records[0]["issues"] == ["asr_transcript", "structure_unparsed"]
    assert records[1]["issues"] == ["structure_unparsed"]
