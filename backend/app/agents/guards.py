"""Prompt 注入防护（安全整改 T3）。

背景：Agent 的输入来自用户上传的对话数据（不可信），可能包含「忽略之前的指令」
一类注入文本。本模块提供**最小可行**防护：

1. ``scan_prompt_injection``：正则匹配常见中/英注入模式，返回命中的规则名；
2. ``neutralize_prompt_injection``：把命中片段替换为 ``[filtered]``；
3. ``neutralize_payload``：递归处理 dict/list，供 ``BaseAgent.invoke`` 统一调用。

约定：
- **只中和显式指令模式**，不改动普通业务文本（避免误伤对话数据）；
- 命中信息写入 ``AgentResult.warnings`` 与 ``metadata.input_guard_hits``，便于审计；
- 正则不是万能防线，Prompt 结构化约束（数据与指令分离）仍需在 Prompt 层配合。
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

FILTERED_MARKER = "[filtered]"
MAX_HITS = 5

# (规则名, 正则)。大小写不敏感；``[^.。\n]`` 限制跨句匹配，降低误报。
_INJECTION_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "ignore_instructions",
        re.compile(
            r"\b(?:ignore|disregard|forget)\b[^.。\n]{0,40}?"
            r"\b(?:previous|prior|above|system|all)\b[^.。\n]{0,20}?"
            r"\b(?:instructions?|prompts?|rules?|directions?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "role_override",
        re.compile(
            r"\b(?:you are now|from now on,? you are|act as an?)\b" r"[^.。\n]{0,30}",
            re.IGNORECASE,
        ),
    ),
    (
        "system_prompt_leak",
        re.compile(
            r"\b(?:reveal|show|print|repeat|output|tell me)\b[^.。\n]{0,30}?"
            r"\b(?:system prompt|hidden prompt|initial instructions)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "jailbreak",
        re.compile(
            r"\b(?:jailbreak|developer mode|DAN mode|do anything now)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "zh_ignore_instructions",
        re.compile(r"(?:忽略|无视|忘记|跳过|不要遵守)[^。！？\n]{0,15}?" r"(?:指令|提示词|设定|要求|规则|限制|约束)"),
    ),
    (
        "zh_role_override",
        re.compile(r"(?:你现在是|从现在开始你是|你不再是|扮演一个没有限制)"),
    ),
    (
        "zh_prompt_leak",
        re.compile(r"(?:重复|输出|打印|告诉我|展示)[^。！？\n]{0,15}?" r"(?:系统提示词|系统指令|隐藏指令|初始指令|上面的提示)"),
    ),
)


def scan_prompt_injection(text: str) -> list[str]:
    """返回命中的规则名（去重、最多 ``MAX_HITS`` 条）。"""
    if not text:
        return []
    hits: list[str] = []
    for name, pattern in _INJECTION_RULES:
        if pattern.search(text):
            hits.append(name)
            if len(hits) >= MAX_HITS:
                break
    return hits


def neutralize_prompt_injection(text: str) -> tuple[str, list[str]]:
    """中和单段文本；返回 ``(处理后的文本, 命中规则)``。"""
    hits = scan_prompt_injection(text)
    if not hits:
        return text, []
    cleaned = text
    for _, pattern in _INJECTION_RULES:
        cleaned = pattern.sub(FILTERED_MARKER, cleaned)
    return cleaned, hits


def neutralize_payload(value: Any, *, path: str = "") -> tuple[Any, list[str]]:
    """递归中和 payload 中的字符串值；返回 ``(新 payload, 命中记录)``。

    命中记录形如 ``"dialogue.user_message:zh_ignore_instructions"``，便于定位。
    """
    if isinstance(value, str):
        cleaned, hits = neutralize_prompt_injection(value)
        if not hits:
            return value, []
        label = path or "input"
        return cleaned, [f"{label}:{hit}" for hit in hits]
    if isinstance(value, Mapping):
        cleaned_map: dict[Any, Any] = {}
        found: list[str] = []
        for key, item in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            cleaned_item, item_hits = neutralize_payload(item, path=child_path)
            cleaned_map[key] = cleaned_item
            found.extend(item_hits)
        return cleaned_map, found
    if isinstance(value, (list, tuple)):
        cleaned_items = []
        found = []
        for index, item in enumerate(value):
            child_path = f"{path}[{index}]" if path else f"[{index}]"
            cleaned_item, item_hits = neutralize_payload(item, path=child_path)
            cleaned_items.append(cleaned_item)
            found.extend(item_hits)
        return type(value)(cleaned_items) if isinstance(value, tuple) else cleaned_items, found
    return value, []


__all__ = [
    "FILTERED_MARKER",
    "neutralize_payload",
    "neutralize_prompt_injection",
    "scan_prompt_injection",
]
