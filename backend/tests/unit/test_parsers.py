"""B-304 文件解析器测试（CSV/JSON/XLSX/TXT）。"""
from __future__ import annotations

import json
from io import BytesIO

import pytest
from openpyxl import Workbook

from app.services.parsers import ParseError, parse_upload

pytestmark = pytest.mark.unit


def _xlsx_bytes() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["user_message", "ai_response"])
    sheet.append(["你好", "您好"])
    sheet.append(["多少钱", "5999 元"])
    buffer = BytesIO()
    workbook.save(buffer)
    workbook.close()
    return buffer.getvalue()


def test_parse_csv() -> None:
    content = "user_message,ai_response\n你好,您好\n价格,5999\n".encode()

    parsed = parse_upload(content, "data.csv")

    assert parsed.format == "csv"
    assert parsed.record_count == 2
    assert parsed.records[0]["user_message"] == "你好"
    assert "价格" in parsed.raw_text


def test_parse_csv_rejects_column_mismatch() -> None:
    """表头 6 列、数据 7 列时必须拒绝：否则字段错位后仍会「成功」入库。

    真实样本（`语流毕昇_可沉淀知识_300.csv`）就缺了 `category_l1` 表头，
    结果 `ai_response` 变成了「知识类,客户反馈…」，静默污染数据。
    """
    content = "q,a,b,c,d,e\n1,2,3,4,5,6,7\n".encode()

    with pytest.raises(ParseError) as excinfo:
        parse_upload(content, "bad.csv")

    assert "第 2 行" in str(excinfo.value)
    assert "表头 6 列" in str(excinfo.value)


def test_parse_csv_allows_blank_lines() -> None:
    content = "q,a\n1,2\n\n3,4\n".encode()

    parsed = parse_upload(content, "ok.csv")

    assert parsed.record_count == 2


def test_parse_json_list() -> None:
    content = b'[{"q": "a", "a": "b"}, {"q": "c", "a": "d"}]'

    parsed = parse_upload(content, "data.json")

    assert parsed.format == "json"
    assert parsed.record_count == 2
    assert parsed.records[1]["q"] == "c"


def test_parse_json_with_data_key() -> None:
    content = b'{"data": [{"q": "a"}]}'

    parsed = parse_upload(content, "data.json")

    assert parsed.record_count == 1
    assert parsed.records[0]["q"] == "a"


def test_parse_xlsx() -> None:
    parsed = parse_upload(_xlsx_bytes(), "data.xlsx")

    assert parsed.format == "xlsx"
    assert parsed.encoding is None
    assert parsed.record_count == 2
    assert parsed.records[0]["user_message"] == "你好"


def test_parse_xlsx_raw_text_is_row_json() -> None:
    """xlsx 没有原文：raw_text 必须是逐行 JSON，否则清洗 Agent 拿不到对话内容。"""
    parsed = parse_upload(_xlsx_bytes(), "data.xlsx")

    assert parsed.raw_text
    rows = json.loads(parsed.raw_text)
    assert rows[0]["user_message"] == "你好"
    assert rows[1]["ai_response"] == "5999 元"


def test_parse_txt() -> None:
    parsed = parse_upload("第一行\n\n第二行\n".encode(), "data.txt")

    assert parsed.format == "txt"
    assert parsed.record_count == 2
    assert parsed.records[1]["text"] == "第二行"


def test_parse_gbk_txt() -> None:
    parsed = parse_upload("客户：你好".encode("gb18030"), "data.txt")

    assert parsed.records[0]["text"] == "客户：你好"
    assert parsed.encoding == "gb18030"


@pytest.mark.parametrize(
    ("content", "filename"),
    [
        (b"%PDF-1.4", "a.pdf"),
        (b"", "data.csv"),
        (b"a,b\n", "data.csv"),
        (b"{invalid json", "data.json"),
        (b"", "data.txt"),
    ],
)
def test_parse_errors(content: bytes, filename: str) -> None:
    with pytest.raises(ParseError):
        parse_upload(content, filename)


def test_parse_invalid_xlsx_raises() -> None:
    with pytest.raises(ParseError):
        parse_upload(b"not-an-xlsx", "data.xlsx")
