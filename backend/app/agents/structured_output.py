"""结构化输出兜底（B-309；06-成本超限降级策略 §3.5）。

流程（最多 2 次）：
1. 从模型输出中提取 JSON → ``schema.model_validate_json``；
2. 失败时把「原始输出 + 校验错误 + JSON Schema」回喂模型修复一次；
3. 仍失败抛 ``StructuredOutputError``（不写库，由调用方转人工/标记失败）。

修复调用产生的 token 由调用方通过 ``usage_collector`` 回收，保证成本口径完整。
"""
from __future__ import annotations

import json
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.core.llm import LLMClient, LLMUsage

TModel = TypeVar("TModel", bound=BaseModel)

_REPAIR_SYSTEM_PROMPT = """你是结构化输出修复器。
用户会给出模型的原始输出与校验错误，请**只输出**符合下列 JSON Schema 的合法 JSON，
不要输出解释、Markdown 代码块或多余文本。

JSON Schema:
{schema}
"""


class StructuredOutputError(Exception):
    """结构化输出在修复后仍不合法（不可重试）。"""

    retryable = False

    def __init__(
        self,
        message: str,
        *,
        raw_output: str | None = None,
        validation_errors: str | None = None,
    ) -> None:
        super().__init__(message)
        self.raw_output = raw_output
        self.validation_errors = validation_errors


def extract_json_text(text: str) -> str:
    """从可能带 Markdown 代码块/前后缀的输出中提取 JSON 文本。"""
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        first_newline = cleaned.find("\n")
        cleaned = cleaned[first_newline + 1 :] if first_newline != -1 else cleaned
        if cleaned.rstrip().endswith("```"):
            cleaned = cleaned.rstrip()[:-3]
        cleaned = cleaned.strip()

    starts = [index for index in (cleaned.find("{"), cleaned.find("[")) if index != -1]
    if not starts:
        return cleaned
    start = min(starts)
    end = max(cleaned.rfind("}"), cleaned.rfind("]"))
    if end > start:
        return cleaned[start : end + 1]
    return cleaned


async def parse_with_repair(
    *,
    text: str,
    schema: type[TModel],
    llm: LLMClient,
    max_attempts: int = 2,
    usage_collector: list[LLMUsage] | None = None,
) -> TModel:
    """解析结构化输出；失败时调用模型修复一次。"""
    raw_output = text
    last_error: Exception | None = None

    for attempt in range(max_attempts):
        try:
            return schema.model_validate_json(extract_json_text(raw_output))
        except (ValidationError, ValueError) as exc:
            last_error = exc
            if attempt + 1 >= max_attempts:
                break

            schema_text = json.dumps(schema.model_json_schema(), ensure_ascii=False)
            repair_messages = [
                {
                    "role": "system",
                    "content": _REPAIR_SYSTEM_PROMPT.format(schema=schema_text),
                },
                {
                    "role": "user",
                    "content": (f"原始输出：\n{raw_output}\n\n" f"校验错误：{exc}\n" "请返回修复后的 JSON。"),
                },
            ]
            response = await llm.chat(
                repair_messages,
                temperature=0.0,
                response_format={"type": "json_object"},
            )
            if usage_collector is not None:
                usage_collector.append(response.usage)
            raw_output = response.content

    raise StructuredOutputError(
        "structured output is still invalid after repair",
        raw_output=raw_output,
        validation_errors=str(last_error),
    )


__all__ = ["StructuredOutputError", "extract_json_text", "parse_with_repair"]
