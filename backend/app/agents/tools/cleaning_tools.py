"""清洗工具集（B-311；Agent 详细设计 §2）。

全部为**纯 Python 函数**（无 LLM、无副作用），供 Agent 与 Service 复用：
``parse_csv`` / ``parse_json`` / ``detect_duplicates`` / ``normalize_text`` /
``extract_timestamp``。
"""
from __future__ import annotations

import csv
import json
import re
from datetime import datetime
from difflib import SequenceMatcher
from io import StringIO
from typing import Any

_ZERO_WIDTH = re.compile(r"[\u200b-\u200d\ufeff]")
_WHITESPACE = re.compile(r"\s+")
_TIMESTAMP_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})"),
        "%Y-%m-%d %H:%M:%S",
    ),
    (
        re.compile(r"(\d{4})/(\d{2})/(\d{2})[ T](\d{2}):(\d{2}):(\d{2})"),
        "%Y/%m/%d %H:%M:%S",
    ),
    (re.compile(r"(\d{4})-(\d{2})-(\d{2})"), "%Y-%m-%d"),
    (re.compile(r"(\d{4})/(\d{2})/(\d{2})"), "%Y/%m/%d"),
    (
        re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2}):(\d{2})"),
        "%Y年%m月%d日 %H:%M",
    ),
)


def normalize_text(text: str) -> str:
    """标准化文本：去零宽字符、统一空白、去首尾空格。"""
    cleaned = _ZERO_WIDTH.sub("", text or "")
    return _WHITESPACE.sub(" ", cleaned).strip()


def parse_csv(text: str) -> list[dict[str, Any]]:
    """解析 CSV 文本为行字典（空行忽略，值去首尾空格）。"""
    reader = csv.DictReader(StringIO(text or ""))
    rows: list[dict[str, Any]] = []
    for row in reader:
        if not any(value for value in row.values() if value not in (None, "")):
            continue
        rows.append(
            {
                (key or "").strip(): (value or "").strip()
                for key, value in row.items()
                if key is not None
            }
        )
    return rows


def parse_json(text: str) -> list[dict[str, Any]]:
    """解析 JSON 文本；支持数组、``{"data": [...]}`` / ``{"records": [...]}`` 与单对象。"""
    data = json.loads(text or "")
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        nested = data.get("data") or data.get("records")
        items = nested if isinstance(nested, list) else [data]
    else:
        items = [data]
    return [item if isinstance(item, dict) else {"value": item} for item in items]


def similarity(left: str, right: str) -> float:
    """文本相似度（0-1，序列匹配）。"""
    return SequenceMatcher(None, normalize_text(left), normalize_text(right)).ratio()


def _dialogue_text(item: str | dict[str, Any]) -> str:
    if isinstance(item, str):
        return item
    return normalize_text(f"{item.get('user_message', '')} {item.get('ai_response', '')}")


def detect_duplicates(
    items: list[str | dict[str, Any]], *, threshold: float = 0.95
) -> list[tuple[int, int]]:
    """返回相似度 ≥ ``threshold`` 的下标对（默认 95%）。"""
    texts = [_dialogue_text(item) for item in items]
    duplicates: list[tuple[int, int]] = []
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            if similarity(texts[i], texts[j]) >= threshold:
                duplicates.append((i, j))
    return duplicates


def extract_timestamp(text: str) -> datetime | None:
    """从文本中提取时间戳（ISO / 斜杠 / 中文日期），失败返回 None。"""
    cleaned = text or ""
    for pattern, fmt in _TIMESTAMP_PATTERNS:
        match = pattern.search(cleaned)
        if match is None:
            continue
        try:
            return datetime.strptime(match.group(0).strip(), fmt)
        except ValueError:
            continue
    return None


__all__ = [
    "detect_duplicates",
    "extract_timestamp",
    "normalize_text",
    "parse_csv",
    "parse_json",
    "similarity",
]
