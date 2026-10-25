"""B-504 / B-505 知识提取 Agent 与 Prompt 资产测试。"""
from __future__ import annotations

import json
import uuid
from typing import Any

import pytest

from app.agents.base import AgentConfig
from app.agents.extraction_agent import PROMPT_DIR, KnowledgeExtractionAgent
from app.core.config import settings
from app.core.llm import LLMResponse, LLMUsage
from app.services import embedding_service

pytestmark = pytest.mark.unit

_DIM = settings.EMBEDDING_DIM


def _fake_encode(texts: list[str], **kwargs: Any) -> list[list[float]]:
    return [[0.25] * _DIM for _ in texts]


class _FakeLLM:
    def __init__(self, script: list[Any]) -> None:
        self._script = list(script)
        self.calls: list[Any] = []

    async def chat(self, messages, **kwargs) -> LLMResponse:  # noqa: ANN001
        self.calls.append(messages)
        item = self._script.pop(0) if self._script else _valid_output()
        if isinstance(item, BaseException):
            raise item
        return LLMResponse(
            content=item,
            usage=LLMUsage(input_tokens=100, output_tokens=80),
            model="fake-model",
            latency_ms=10.0,
        )


def _valid_output(
    faqs: list[dict[str, Any]] | None = None,
    gaps: list[dict[str, Any]] | None = None,
) -> str:
    payload = {
        "faqs": faqs
        if faqs is not None
        else [
            {
                "question": "iPhone 14 多少钱？",
                "answer": "5999 元起，支持 12 期免息。",
                "category": "价格",
                "variations": ["iPhone 14 价格"],
                "confidence": 0.95,
                "source_dialogue_ids": ["1"],
            },
            {
                "question": "多久发货？",
                "answer": "48 小时内发出。",
                "category": "物流",
                "variations": ["什么时候发货"],
                "confidence": 0.9,
                "source_dialogue_ids": ["2"],
            },
        ],
        "gaps": gaps
        if gaps is not None
        else [{"question": "能否开发票？", "reason": "未覆盖", "frequency": 2}],
    }
    return json.dumps(payload, ensure_ascii=False)


def _agent(llm: _FakeLLM) -> KnowledgeExtractionAgent:
    return KnowledgeExtractionAgent(
        AgentConfig(name="extraction_agent", max_retries=0, retry_base_delay=0.0),
        llm=llm,
    )


def _input(
    dialogues: list[dict[str, Any]] | None = None,
    existing_questions: list[str] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "datasource_id": str(uuid.uuid4()),
        "dialogues": dialogues
        if dialogues is not None
        else [
            {
                "dialogue_id": "1",
                "user_message": "iPhone 14 多少钱",
                "ai_response": "5999 元起",
            }
        ],
        "existing_questions": existing_questions or [],
        "config": config or {},
    }


def test_prompt_assets() -> None:
    system = (PROMPT_DIR / "system.txt").read_text(encoding="utf-8")
    examples = json.loads((PROMPT_DIR / "examples.json").read_text(encoding="utf-8"))
    version = (PROMPT_DIR / "version.txt").read_text(encoding="utf-8")

    assert "faqs" in system and "gaps" in system
    assert len(examples) >= 6
    assert all("input" in item and "output" in item for item in examples)
    assert version.strip().startswith("v")


async def test_extract_success_with_filters(monkeypatch) -> None:
    monkeypatch.setattr(embedding_service, "encode_texts_sync", _fake_encode)
    faqs = [
        {
            "question": "iPhone 14 多少钱？",
            "answer": "5999 元起。",
            "category": "价格",
            "variations": ["iPhone 14 价格"],
            "confidence": 0.95,
            "source_dialogue_ids": ["1"],
        },
        {
            "question": "低置信问题？",
            "answer": "答案",
            "confidence": 0.3,
        },
        {
            "question": "iPhone 14 多少钱？",
            "answer": "重复答案",
            "confidence": 0.9,
        },
    ]
    llm = _FakeLLM([_valid_output(faqs=faqs)])
    agent = _agent(llm)

    result = await agent.extract(_input())

    assert result.success is True
    data = result.data or {}
    assert len(data["faqs"]) == 1
    assert data["faqs"][0]["question"] == "iPhone 14 多少钱？"
    assert len(data["faqs"][0]["embedding"]) == _DIM
    assert data["stats"]["filtered_low_confidence"] == 1
    assert data["stats"]["duplicates_removed"] == 1
    assert len(data["gaps"]) == 1


async def test_extract_removes_existing_questions(monkeypatch) -> None:
    monkeypatch.setattr(embedding_service, "encode_texts_sync", _fake_encode)
    llm = _FakeLLM([_valid_output()])
    agent = _agent(llm)

    result = await agent.extract(_input(existing_questions=["iphone 14 多少钱？"]))

    data = result.data or {}
    assert len(data["faqs"]) == 1
    assert data["stats"]["duplicates_removed"] == 1


async def test_extract_embedding_failure_does_not_block(monkeypatch) -> None:
    def _broken(texts: list[str], **kwargs: Any) -> list[list[float]]:
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(embedding_service, "encode_texts_sync", _broken)
    llm = _FakeLLM([_valid_output()])
    agent = _agent(llm)

    result = await agent.extract(_input())

    data = result.data or {}
    assert result.success is True
    assert len(data["faqs"]) == 2
    assert all(item["embedding"] is None for item in data["faqs"])
    assert data["stats"]["embedding_failed"] == 2
    assert data["stats"]["warnings"]


async def test_extract_respects_max_faqs_and_gap_switch(monkeypatch) -> None:
    monkeypatch.setattr(embedding_service, "encode_texts_sync", _fake_encode)
    llm = _FakeLLM([_valid_output()])
    agent = _agent(llm)

    result = await agent.extract(_input(config={"max_faqs": 1, "include_gaps": False}))

    data = result.data or {}
    assert len(data["faqs"]) == 1
    assert data["gaps"] == []


async def test_extract_invalid_input(monkeypatch) -> None:
    monkeypatch.setattr(embedding_service, "encode_texts_sync", _fake_encode)
    llm = _FakeLLM([])
    agent = _agent(llm)

    result = await agent.extract(_input(dialogues=[]))

    assert result.success is False
    assert any("AgentInputError" in item for item in result.errors)
    assert llm.calls == []


async def test_extract_repairs_invalid_json(monkeypatch) -> None:
    monkeypatch.setattr(embedding_service, "encode_texts_sync", _fake_encode)
    llm = _FakeLLM(["not json", _valid_output()])
    agent = _agent(llm)

    result = await agent.extract(_input())

    assert result.success is True
    assert len(llm.calls) == 2
