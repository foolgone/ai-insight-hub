"""长转写分块与合并单测（修复「39 分钟录音 → 一整段」）。"""
from __future__ import annotations

import pytest

from app.agents.structure_agent import TranscriptStructureAgent
from app.agents.structured_output import parse_with_repair
from app.application.structure_service import (
    CHUNK_MAX_CHARS,
    merge_payloads,
    split_transcript,
)
from app.core.llm import LLMResponse, LLMUsage
from app.schemas.agents.structure import StructureOutput

pytestmark = pytest.mark.unit


def _long_text(sentences: int, sentence: str = "面试官：请介绍一下你的项目经历。") -> str:
    return "".join(sentence for _ in range(sentences))


def test_short_text_kept_as_single_chunk() -> None:
    assert split_transcript("只有一句话。") == ["只有一句话。"]


def test_split_respects_sentence_boundaries_and_size() -> None:
    text = _long_text(40)  # ≈ 720 字，切成多块
    chunks = split_transcript(text, max_chars=200)

    assert len(chunks) > 1
    assert all(len(chunk) <= 200 for chunk in chunks)
    # 不丢内容（只比较非空白字符）
    assert "".join(chunks).replace(" ", "") == text.replace(" ", "")
    # 每块都以句末标点结尾（按句切，不切断句子）
    assert all(chunk.endswith("。") for chunk in chunks)


def test_single_huge_sentence_is_hard_split() -> None:
    text = "啊" * 700  # ASR 没标点的情况

    chunks = split_transcript(text, max_chars=200)

    assert len(chunks) == 4
    assert "".join(chunks) == text


def test_chunk_count_capped_without_losing_content() -> None:
    text = _long_text(200)
    chunks = split_transcript(text, max_chars=100, max_chunks=3)

    assert len(chunks) == 3
    assert "".join(chunks).replace(" ", "") == text.replace(" ", "")


def test_merge_prefers_qa_and_deduplicates() -> None:
    merged = merge_payloads(
        [
            {
                "content_type": "interview",
                "structure": "qa",
                "confidence": 0.8,
                "qa": [
                    {"question": "你做过什么项目？", "answer": "综合执法平台", "quality_score": 70},
                ],
            },
            {
                "content_type": "interview",
                "structure": "qa",
                "confidence": 0.9,
                "qa": [
                    # 同一组问答（空格差异）→ 去重，保留更高分
                    {"question": "你做过什么 项目？", "answer": "综合执法平台", "quality_score": 85},
                    {"question": "为什么离职？", "answer": "想换个方向", "quality_score": 60},
                ],
            },
        ]
    )

    assert merged["structure"] == "qa"
    assert len(merged["qa"]) == 2
    assert merged["qa"][0]["quality_score"] == 85
    assert merged["content_type"] == "interview"
    assert merged["confidence"] == 0.85
    assert merged["merge"]["chunks"] == 2


def test_merge_falls_back_to_knowledge_then_summary() -> None:
    knowledge = merge_payloads(
        [
            {"structure": "knowledge", "knowledge": [{"title": "索引", "content": "看执行计划"}]},
            {"structure": "summary", "summary": "讨论了数据库优化。"},
        ]
    )
    assert knowledge["structure"] == "knowledge"
    assert knowledge["knowledge"][0]["title"] == "索引"

    summary = merge_payloads(
        [
            {"structure": "summary", "summary": "第一块摘要。"},
            {"structure": "summary", "summary": "第二块摘要。"},
        ]
    )
    assert summary["structure"] == "summary"
    assert "第一块摘要" in summary["summary"]
    assert "第二块摘要" in summary["summary"]


def test_merge_requires_at_least_one_payload() -> None:
    with pytest.raises(ValueError):
        merge_payloads([])


def test_business_validator_rejects_empty_content() -> None:
    agent = TranscriptStructureAgent()

    with pytest.raises(ValueError, match="qa is empty"):
        agent._validate_parsed(  # noqa: SLF001 - 直接测业务校验
            StructureOutput(content_type="interview", structure="qa", qa=[])
        )

    with pytest.raises(ValueError, match="summary is empty"):
        agent._validate_parsed(  # noqa: SLF001
            StructureOutput(content_type="meeting", structure="summary", summary="   ")
        )

    with pytest.raises(ValueError, match="knowledge is empty"):
        agent._validate_parsed(  # noqa: SLF001
            StructureOutput(content_type="other", structure="knowledge", knowledge=[])
        )


def test_business_validator_accepts_valid_forms() -> None:
    agent = TranscriptStructureAgent()
    agent._validate_parsed(  # noqa: SLF001
        StructureOutput(
            content_type="interview",
            structure="qa",
            qa=[{"question": "q", "answer": "a"}],
        )
    )
    agent._validate_parsed(  # noqa: SLF001
        StructureOutput(content_type="meeting", structure="summary", summary="有内容的摘要")
    )


class _StubLLM:
    def __init__(self, contents: list[str]) -> None:
        self._contents = list(contents)
        self.calls: list[list[dict]] = []

    async def chat(self, messages, **kwargs) -> LLMResponse:  # noqa: ANN001
        self.calls.append(list(messages))
        content = self._contents.pop(0) if self._contents else "{}"
        return LLMResponse(
            content=content,
            usage=LLMUsage(input_tokens=10, output_tokens=5),
            model="stub-model",
            latency_ms=5.0,
        )


async def test_repair_retries_when_business_validation_fails() -> None:
    """模型先返回「合法但空」的 qa，业务校验失败 → 修复轮拿到明确指令并返回有效内容。"""
    agent = TranscriptStructureAgent()
    repaired = (
        '{"content_type": "interview", "structure": "qa",'
        ' "qa": [{"question": "请介绍一下项目", "answer": "做过综合执法平台"}]}'
    )
    llm = _StubLLM([repaired])
    collector: list[LLMUsage] = []

    result = await parse_with_repair(
        text='{"content_type": "interview", "structure": "qa", "qa": []}',
        schema=StructureOutput,
        llm=llm,
        usage_collector=collector,
        validator=agent._validate_parsed,  # noqa: SLF001
    )

    assert result.structure == "qa"
    assert result.qa
    assert len(llm.calls) == 1  # 触发了一次修复
    assert len(collector) == 1
    repair_prompt = llm.calls[0][1]["content"]
    assert "qa is empty" in repair_prompt
    assert "不得返回空字符串或空数组" in repair_prompt


def test_chunk_size_constant_is_sane() -> None:
    # 每块上限应小于结构化 Agent 的输入上限，且能容纳 2-3 分钟的转写内容
    assert 1000 <= CHUNK_MAX_CHARS <= 5000
