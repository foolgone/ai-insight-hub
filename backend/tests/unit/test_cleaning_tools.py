"""B-311 清洗工具集测试。"""
from __future__ import annotations

from datetime import datetime

import pytest

from app.agents.tools.cleaning_tools import (
    detect_duplicates,
    extract_timestamp,
    normalize_text,
    parse_csv,
    parse_json,
    similarity,
)

pytestmark = pytest.mark.unit


def test_parse_csv() -> None:
    rows = parse_csv("user_message,ai_response\n 你好 , 您好 \n多少钱,5999\n")

    assert rows == [
        {"user_message": "你好", "ai_response": "您好"},
        {"user_message": "多少钱", "ai_response": "5999"},
    ]


def test_parse_csv_ignores_blank_lines() -> None:
    rows = parse_csv("a,b\n1,2\n,\n3,4\n")

    assert [row["a"] for row in rows] == ["1", "3"]


def test_parse_json_list_and_nested() -> None:
    assert parse_json('[{"q": "a"}]') == [{"q": "a"}]
    assert parse_json('{"data": [{"q": "b"}]}') == [{"q": "b"}]
    assert parse_json('{"records": [{"q": "c"}]}') == [{"q": "c"}]


def test_parse_json_single_object() -> None:
    assert parse_json('{"q": "only"}') == [{"q": "only"}]
    assert parse_json("[1, 2]") == [{"value": 1}, {"value": 2}]


def test_normalize_text() -> None:
    assert normalize_text("  hello\u200b   world \n second  ") == "hello world second"
    assert normalize_text("") == ""


def test_similarity() -> None:
    assert similarity("你好 世界", "你好   世界") == pytest.approx(1.0)
    assert similarity("你好世界", "你好世界") == pytest.approx(1.0)
    assert similarity("苹果", "香蕉") < 0.5


def test_detect_duplicates_by_threshold() -> None:
    items = [
        "用户：退货怎么操作 客服：在订单页申请",
        "用户：退货怎么操作 客服：在订单页申请",
        "用户：发票怎么开 客服：下单填写抬头",
    ]

    duplicates = detect_duplicates(items)

    assert duplicates == [(0, 1)]


def test_detect_duplicates_with_dicts_and_custom_threshold() -> None:
    items = [
        {"user_message": "价格", "ai_response": "5999"},
        {"user_message": "价格", "ai_response": "5999 元"},
    ]

    assert detect_duplicates(items, threshold=0.5) == [(0, 1)]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("2025-01-15 10:30:00 客户：你好", datetime(2025, 1, 15, 10, 30, 0)),
        ("2025/01/16 09:05:00 客户：你好", datetime(2025, 1, 16, 9, 5, 0)),
        ("2025-01-15 客户：你好", datetime(2025, 1, 15)),
        ("2025年1月15日 10:30 客户：你好", datetime(2025, 1, 15, 10, 30)),
        ("没有时间信息", None),
        ("2025-13-45", None),
    ],
)
def test_extract_timestamp(text: str, expected: datetime | None) -> None:
    assert extract_timestamp(text) == expected
