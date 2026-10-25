"""B-309 结构化输出兜底测试。"""
from __future__ import annotations

import pytest
from pydantic import BaseModel

from app.agents.structured_output import (
    StructuredOutputError,
    extract_json_text,
    parse_with_repair,
)
from app.core.llm import LLMResponse, LLMUsage

pytestmark = pytest.mark.unit


class _Answer(BaseModel):
    answer: str


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


def test_extract_json_from_code_fence() -> None:
    text = '```json\n{"answer": "ok"}\n```'

    assert extract_json_text(text) == '{"answer": "ok"}'


def test_extract_json_with_preamble_and_suffix() -> None:
    text = '解析结果如下：{"answer": "ok"} 谢谢'

    assert extract_json_text(text) == '{"answer": "ok"}'


def test_extract_json_array() -> None:
    assert extract_json_text("[1, 2, 3]") == "[1, 2, 3]"


async def test_parse_success_without_repair() -> None:
    llm = _StubLLM([])

    result = await parse_with_repair(text='{"answer": "ok"}', schema=_Answer, llm=llm)

    assert result.answer == "ok"
    assert llm.calls == []


async def test_parse_repairs_once_and_collects_usage() -> None:
    llm = _StubLLM(['{"answer": "fixed"}'])
    collector: list[LLMUsage] = []

    result = await parse_with_repair(
        text="not json at all",
        schema=_Answer,
        llm=llm,
        usage_collector=collector,
    )

    assert result.answer == "fixed"
    assert len(llm.calls) == 1
    assert len(collector) == 1
    assert collector[0].total_tokens == 15


async def test_parse_fails_after_one_repair() -> None:
    llm = _StubLLM(["still not json"])

    with pytest.raises(StructuredOutputError) as exc_info:
        await parse_with_repair(text="bad", schema=_Answer, llm=llm)

    assert len(llm.calls) == 1
    assert exc_info.value.raw_output == "still not json"
    assert exc_info.value.validation_errors
    assert exc_info.value.retryable is False
