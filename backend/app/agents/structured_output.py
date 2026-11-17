"""结构化输出兜底（B-309；06-成本超限降级策略 §3.5）。

流程（最多 2 次）：
1. 从模型输出中提取 JSON → ``schema.model_validate_json``；
2. 失败时把「原始输出 + 校验错误 + JSON Schema」回喂模型修复一次；
3. 仍失败抛 ``StructuredOutputError``（不写库，由调用方转人工/标记失败）。

修复调用产生的 token 由调用方通过 ``usage_collector`` 回收，保证成本口径完整。
"""
from __future__ import annotations

import json
from collections.abc import Callable
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.core.llm import LLMUsage
from app.ports.llm import LLMPort

TModel = TypeVar("TModel", bound=BaseModel)

_REPAIR_SYSTEM_PROMPT = """你是结构化输出修复器。
只输出合法 JSON，不要输出解释、Markdown 代码块或多余文本。
必须保留原输出表达的含义；字段名、层级和类型必须与示例/JSON Schema 一致。
{example}
"""


class StructuredOutputError(Exception):
    """结构化输出在修复后仍不合法（不可重试）。"""

    retryable = False

    def __init__(
        self,
        message: str,
        *,
        original_output: str | None = None,
        raw_output: str | None = None,
        validation_errors: str | None = None,
    ) -> None:
        super().__init__(message)
        # 首次输出与最后一次（修复轮）输出分开保留，便于定位非法点。
        self.original_output = original_output
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
    llm: LLMPort,
    max_attempts: int = 2,
    usage_collector: list[LLMUsage] | None = None,
    validator: Callable[[TModel], None] | None = None,
    raw_sink: list[str] | None = None,
    repair_example: str | None = None,
) -> TModel:
    """解析结构化输出；失败时调用模型修复一次。

    ``validator`` 用于**业务校验**（schema 合法但内容不可用，例如
    ``structure=summary`` 却 ``summary`` 为空）。这类错误同样会进入修复轮，
    否则模型返回一个「最小合法但空」的对象就能让整条链路静默降级。

    ``raw_sink`` 用于记录**最终实际用于解析**的原文（可能是修复轮的输出），
    供评测链路保存 Judge 原始响应；不传则行为不变。

    ``repair_example`` 是一条完整合法 JSON 示例；提供时修复 Prompt 不再 dump
    完整 JSON Schema，避免长 schema + 长原文导致模型输出半截 JSON。未提供时
    fallback 到 ``json.dumps(schema.model_json_schema())``，保持其它 Agent 的修复能力。
    """
    original_output = text
    raw_output = text
    last_error: Exception | None = None

    for attempt in range(max_attempts):
        try:
            model = schema.model_validate_json(extract_json_text(raw_output))
            if validator is not None:
                validator(model)
            if raw_sink is not None:
                raw_sink.append(raw_output)
            return model
        except (ValidationError, ValueError) as exc:
            last_error = exc
            if attempt + 1 >= max_attempts:
                break

            example_block = (
                f"合法 JSON 示例：\n{repair_example}\n"
                if repair_example
                else "参考以下 JSON Schema：\n"
                + json.dumps(schema.model_json_schema(), ensure_ascii=False)
                + "\n"
            )
            repair_messages = [
                {
                    "role": "system",
                    "content": _REPAIR_SYSTEM_PROMPT.format(example=example_block),
                },
                {
                    "role": "user",
                    "content": (
                        f"原始输出：\n{raw_output}\n\n"
                        f"校验错误：{exc}\n\n"
                        "请返回修复后的 JSON。若错误指出字段为空/缺失，"
                        "必须用原文中的真实内容补全，不得返回空字符串或空数组，不得编造。"
                    ),
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
        original_output=original_output,
        raw_output=raw_output,
        validation_errors=str(last_error),
    )


__all__ = ["StructuredOutputError", "extract_json_text", "parse_with_repair"]
