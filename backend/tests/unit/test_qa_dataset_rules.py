"""数据集规则单测：checksum 稳定性 + 导入校验（Phase 1）。

checksum 的契约（改动必须同步这里）：
- 范围：item_key / query / gold_answer / gold_evidence / category / difficulty /
  source / split / metadata；
- 条目按 item_key 排序、证据按 (document_id, chunk_id, evidence_text, page_number) 排序；
- 规范化 JSON（sort_keys + 紧凑分隔符 + 非 ASCII 原样）后 sha256。
"""
from __future__ import annotations

import pytest

from app.services.qa_dataset_service import (
    CHECKSUM_FIELDS,
    canonical_item,
    compute_checksum,
    validate_import_payload,
)

pytestmark = pytest.mark.unit


def _item(**overrides) -> dict:
    base = {
        "item_key": "Q001",
        "query": "如何申请退款？",
        "gold_answer": "在订单页申请退款。",
        "gold_evidence": [
            {
                "document_id": "doc-1",
                "chunk_id": "chunk-1",
                "evidence_text": "订单详情页提供申请退款入口。",
                "page_number": 3,
                "metadata": {"section": "售后"},
            }
        ],
        "category": "售后",
        "difficulty": "easy",
        "source": "doc:robot-backend",
        "split": "test",
        "metadata": {"source_doc": "设置.docx"},
    }
    base.update(overrides)
    return base


# --------------------------------------------------------------------------- checksum


def test_checksum_fields_cover_required_semantics() -> None:
    assert set(CHECKSUM_FIELDS) == {
        "item_key",
        "query",
        "gold_answer",
        "gold_evidence",
        "category",
        "difficulty",
        "source",
        "split",
        "metadata",
    }


def test_checksum_is_stable_across_item_and_evidence_order() -> None:
    first = _item()
    second = _item(
        item_key="Q002",
        query="发票怎么开？",
        gold_evidence=[
            {
                "document_id": "doc-2",
                "chunk_id": "chunk-9",
                "evidence_text": "开票入口在订单详情页。",
                "page_number": None,
            }
        ],
    )

    forward = compute_checksum([first, second])
    backward = compute_checksum([second, first])

    assert forward == backward
    assert len(forward) == 64


def test_checksum_ignores_evidence_order_within_item() -> None:
    e1 = {
        "document_id": "doc-1",
        "chunk_id": "c1",
        "evidence_text": "证据一：退款入口在订单页。",
        "page_number": 1,
    }
    e2 = {
        "document_id": "doc-1",
        "chunk_id": "c2",
        "evidence_text": "证据二：退款到账需 1-3 天。",
        "page_number": 2,
    }
    a = compute_checksum([_item(gold_evidence=[e1, e2])])
    b = compute_checksum([_item(gold_evidence=[e2, e1])])

    assert a == b


def test_checksum_changes_when_content_changes() -> None:
    base = compute_checksum([_item()])

    assert compute_checksum([_item(query="如何申请退货？")]) != base
    assert compute_checksum([_item(gold_answer=None)]) != base
    assert compute_checksum([_item(split="train")]) != base
    assert compute_checksum([_item(metadata={"a": 1})]) != base
    changed_evidence = _item()
    changed_evidence["gold_evidence"][0]["evidence_text"] = "另一段证据文本（至少十个字）。"
    assert compute_checksum([changed_evidence]) != base


def test_canonical_item_normalizes_missing_fields() -> None:
    canonical = canonical_item({"item_key": "Q1", "query": " 问题 "})

    assert canonical["query"] == "问题"
    assert canonical["gold_answer"] is None
    assert canonical["split"] == "test"
    assert canonical["gold_evidence"] == []
    assert canonical["metadata"] == {}


# --------------------------------------------------------------------------- 导入校验


def test_validate_import_accepts_valid_batch() -> None:
    validated, errors = validate_import_payload(
        [_item(item_key="Q001"), _item(item_key="Q002")],
        existing_keys=set(),
    )

    assert errors == []
    assert [item.item_key for item in validated] == ["Q001", "Q002"]


def test_validate_import_reports_duplicate_inside_batch() -> None:
    _, errors = validate_import_payload(
        [_item(item_key="Q001"), _item(item_key="Q001")],
        existing_keys=set(),
    )

    assert len(errors) == 1
    assert errors[0]["index"] == 2
    assert errors[0]["field"] == "item_key"
    assert "第 1 行" in errors[0]["message"]


def test_validate_import_reports_existing_key() -> None:
    _, errors = validate_import_payload([_item(item_key="Q001")], existing_keys={"Q001"})

    assert errors[0]["index"] == 1
    assert "已存在" in errors[0]["message"]


def test_validate_import_requires_evidence_text() -> None:
    """只给 document_id 不给证据文本 → 拒收（否则无法复现历史评测）。"""
    raw = _item(item_key="Q001", gold_evidence=[{"document_id": "doc-1"}])

    _, errors = validate_import_payload([raw], existing_keys=set())

    assert errors[0]["index"] == 1
    assert errors[0]["field"].startswith("gold_evidence")
    assert "evidence_text" in errors[0]["field"]


def test_validate_import_rejects_bad_split_and_short_text() -> None:
    raw = _item(item_key="Q001", split="holdout")
    raw["gold_evidence"][0]["evidence_text"] = "太短"

    _, errors = validate_import_payload([raw], existing_keys=set())

    fields = {error["field"] for error in errors}
    assert "split" in fields
    assert any(field.endswith("evidence_text") for field in fields)


def test_validate_import_rejects_non_object_item() -> None:
    _, errors = validate_import_payload(["not-an-object"], existing_keys=set())

    assert errors == [{"index": 1, "field": "item", "message": "条目必须是对象"}]


def test_validate_import_collects_all_rows() -> None:
    raw_items = [
        _item(item_key="Q001"),
        _item(item_key="Q002", gold_evidence=[]),  # 允许：纯检索集可以没有证据
        _item(item_key="Q003", query=""),
        _item(item_key="Q004", split="bad"),
    ]

    validated, errors = validate_import_payload(raw_items, existing_keys=set())

    assert [item.item_key for item in validated] == ["Q001", "Q002"]
    indexes = {error["index"] for error in errors}
    assert indexes == {3, 4}
