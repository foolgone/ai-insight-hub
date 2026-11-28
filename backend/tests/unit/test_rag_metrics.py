"""确定性检索指标表驱动单测（Phase 3A）。

重点验证**公式**（不是「函数能跑」）：
- HitRate / MRR 的 K 截断与排名；
- Context Recall 的 Gold 粒度与去重；
- Context Precision 两个变体的口径差异（P@K vs AP@K）；
- skipped 不返回 0；
- 文本级匹配必须规范化后完全相等（不做包含匹配）。
"""
from __future__ import annotations

import pytest

from app.application.metrics import (
    METRIC_CONTEXT_PRECISION_AP_AT_K,
    METRIC_CONTEXT_PRECISION_AT_K,
    METRIC_CONTEXT_RECALL,
    METRIC_HIT_RATE,
    METRIC_MRR,
    SKIP_GOLD_MISSING,
    SKIP_NO_RETRIEVED,
    EvidenceRef,
    RetrievedItem,
    context_precision_ap_at_k,
    context_precision_at_k,
    context_recall,
    evaluate_retrieval,
    failed_result,
    hit_rate_at_k,
    match_basis,
    mrr_at_k,
    normalize_text,
)

pytestmark = pytest.mark.unit


def doc(document_id: str, content: str = "") -> RetrievedItem:
    return RetrievedItem(document_id=document_id, content=content or f"doc-{document_id}")


# --------------------------------------------------------------------------- HitRate@K


@pytest.mark.parametrize(
    ("retrieved", "gold", "k", "expected_value", "expected_status", "expected_rank"),
    [
        # 完全命中，rank=1
        ([doc("d1")], [EvidenceRef(document_id="d1")], 5, 1.0, "evaluated", 1),
        # 命中在 K 边界
        ([doc("d2"), doc("d1")], [EvidenceRef(document_id="d1")], 2, 1.0, "evaluated", 2),
        # 命中在 K 之外
        ([doc("d2"), doc("d1")], [EvidenceRef(document_id="d1")], 1, 0.0, "evaluated", None),
        # 完全未命中
        ([doc("d9")], [EvidenceRef(document_id="d1")], 5, 0.0, "evaluated", None),
        # 空检索结果
        ([], [EvidenceRef(document_id="d1")], 5, 0.0, "evaluated", None),
        # 空 Gold → skipped（不是 0）
        ([doc("d1")], [], 5, None, "skipped", None),
    ],
)
def test_hit_rate_table(retrieved, gold, k, expected_value, expected_status, expected_rank) -> None:
    result = hit_rate_at_k(retrieved, gold, k=k)

    assert result.metric_name == METRIC_HIT_RATE
    assert result.status == expected_status
    assert result.value == expected_value
    assert result.details["k"] == k
    if expected_status == "skipped":
        assert result.n_skipped == 1 and result.n_evaluated == 0
        assert result.skipped_reason == SKIP_GOLD_MISSING
    else:
        assert result.n_evaluated == 1 and result.n_skipped == 0
        assert result.details["first_match_rank"] == expected_rank


# --------------------------------------------------------------------------- MRR@K


@pytest.mark.parametrize(
    ("retrieved", "gold", "k", "expected_value", "expected_rank"),
    [
        ([doc("d1"), doc("d2")], [EvidenceRef(document_id="d1")], 5, 1.0, 1),
        ([doc("d2"), doc("d1")], [EvidenceRef(document_id="d1")], 5, 0.5, 2),
        ([doc("d2"), doc("d3"), doc("d1")], [EvidenceRef(document_id="d1")], 5, 1 / 3, 3),
        # K 截断后未命中
        ([doc("d2"), doc("d1")], [EvidenceRef(document_id="d1")], 1, 0.0, None),
        # 空检索
        ([], [EvidenceRef(document_id="d1")], 5, 0.0, None),
    ],
)
def test_mrr_table(retrieved, gold, k, expected_value, expected_rank) -> None:
    result = mrr_at_k(retrieved, gold, k=k)

    assert result.metric_name == METRIC_MRR
    assert result.status == "evaluated"
    assert result.value == pytest.approx(expected_value, abs=1e-6)
    assert result.details["first_relevant_rank"] == expected_rank


def test_mrr_skipped_without_gold() -> None:
    result = mrr_at_k([doc("d1")], [], k=5)

    assert result.status == "skipped"
    assert result.value is None
    assert result.skipped_reason == SKIP_GOLD_MISSING


# --------------------------------------------------------------------------- Context Recall


@pytest.mark.parametrize(
    ("retrieved", "gold", "expected_value", "matched_count"),
    [
        # 完全命中
        (
            [doc("d1"), doc("d2")],
            [EvidenceRef(document_id="d1"), EvidenceRef(document_id="d2")],
            1.0,
            2,
        ),
        # 部分命中
        ([doc("d1")], [EvidenceRef(document_id="d1"), EvidenceRef(document_id="d2")], 0.5, 1),
        # 完全未命中
        ([doc("d9")], [EvidenceRef(document_id="d1")], 0.0, 0),
        # 空检索
        ([], [EvidenceRef(document_id="d1")], 0.0, 0),
        # 混合粒度：chunk 级未命中 + 文档级命中
        (
            [RetrievedItem(document_id="d1", chunk_id="c9"), doc("d2")],
            [EvidenceRef(document_id="d1", chunk_id="c1"), EvidenceRef(document_id="d2")],
            0.5,
            1,
        ),
    ],
)
def test_context_recall_table(retrieved, gold, expected_value, matched_count) -> None:
    result = context_recall(retrieved, gold)

    assert result.metric_name == METRIC_CONTEXT_RECALL
    assert result.status == "evaluated"
    assert result.value == pytest.approx(expected_value)
    assert result.details["matched_count"] == matched_count
    assert result.details["gold_count"] == len(gold)


def test_context_recall_skipped_without_gold() -> None:
    result = context_recall([doc("d1")], [])

    assert result.status == "skipped"
    assert result.value is None
    assert result.skipped_reason == SKIP_GOLD_MISSING


# --------------------------------------------------------------------------- Precision@K


@pytest.mark.parametrize(
    ("retrieved", "gold", "k", "expected_value", "relevant_count"),
    [
        # 3 条里 1 条相关 → 1/3
        ([doc("d1"), doc("d2"), doc("d3")], [EvidenceRef(document_id="d1")], 3, 1 / 3, 1),
        # K=1 只看第一条
        ([doc("d1"), doc("d2")], [EvidenceRef(document_id="d1")], 1, 1.0, 1),
        # 全部相关
        (
            [doc("d1"), doc("d2")],
            [EvidenceRef(document_id="d1"), EvidenceRef(document_id="d2")],
            2,
            1.0,
            2,
        ),
        # 全部不相关
        ([doc("d8"), doc("d9")], [EvidenceRef(document_id="d1")], 2, 0.0, 0),
        # 重复检索去重后：d1,d2 → 1/2
        ([doc("d1"), doc("d1"), doc("d2")], [EvidenceRef(document_id="d1")], 3, 0.5, 1),
    ],
)
def test_context_precision_at_k_table(retrieved, gold, k, expected_value, relevant_count) -> None:
    result = context_precision_at_k(retrieved, gold, k=k)

    assert result.metric_name == METRIC_CONTEXT_PRECISION_AT_K
    assert result.status == "evaluated"
    assert result.value == pytest.approx(expected_value)
    assert result.details["mode"] == "precision_at_k"
    assert result.details["relevant_count"] == relevant_count


def test_context_precision_denominator_is_actual_returned_count() -> None:
    """Precision@K 的分母是「实际返回且去重后」的条数，不是固定 K。

    returned=2（< K=5），1 条相关 → 0.5；
    若按固定 K 计算会得到 0.2 —— 本测试锁定「返回相对」语义。
    """
    result = context_precision_at_k([doc("d1"), doc("d2")], [EvidenceRef(document_id="d1")], k=5)

    assert result.value == pytest.approx(0.5)
    assert result.details["returned_count"] == 2
    assert result.details["k"] == 5


def test_same_document_different_chunks_are_not_merged() -> None:
    """同一 document_id 下的不同 chunk 必须保留为两条（按 chunk_id 去重）。"""
    retrieved = [
        RetrievedItem(document_id="d1", chunk_id="c1", content="片段一"),
        RetrievedItem(document_id="d1", chunk_id="c2", content="片段二"),
    ]

    precision = context_precision_at_k(
        retrieved, [EvidenceRef(document_id="d1", chunk_id="c1")], k=5
    )
    recall = context_recall(retrieved, [EvidenceRef(document_id="d1", chunk_id="c1")])

    assert precision.details["returned_count"] == 2
    assert precision.value == pytest.approx(0.5)
    assert recall.value == pytest.approx(1.0)


def test_dedupe_happens_before_k_truncation() -> None:
    """先去重再截断：重复项不占用 K 名额（[d1,d1,d2] + k=2 → d1,d2）。"""
    retrieved = [doc("d1"), doc("d1"), doc("d2")]
    gold = [EvidenceRef(document_id="d1"), EvidenceRef(document_id="d2")]

    result = context_precision_at_k(retrieved, gold, k=2)

    assert result.details["returned_count"] == 2
    assert result.value == pytest.approx(1.0)


def test_context_precision_skips_without_retrieved_or_gold() -> None:
    no_retrieved = context_precision_at_k([], [EvidenceRef(document_id="d1")])
    assert no_retrieved.status == "skipped"
    assert no_retrieved.skipped_reason == SKIP_NO_RETRIEVED

    no_gold = context_precision_at_k([doc("d1")], [])
    assert no_gold.status == "skipped"
    assert no_gold.skipped_reason == SKIP_GOLD_MISSING


# --------------------------------------------------------------------------- AP@K


@pytest.mark.parametrize(
    ("retrieved", "gold", "k", "expected_value", "flags"),
    [
        # gold 1 条，命中在 rank2：P@1=0, P@2=0.5 → AP=0.5/1
        ([doc("d2"), doc("d1")], [EvidenceRef(document_id="d1")], 2, 0.5, [0, 1]),
        # gold 2 条，命中 rank1/rank3：P@1=1, P@2=0.5, P@3=2/3 → AP=(1+0+2/3)/2
        (
            [doc("d1"), doc("d3"), doc("d2")],
            [EvidenceRef(document_id="d1"), EvidenceRef(document_id="d2")],
            3,
            (1 + 0 + 2 / 3) / 2,
            [1, 0, 1],
        ),
        # K 截断：第二条 gold 在 K 外，分母取 min(|G|,K)=2，只累加前 2 名
        (
            [doc("d1"), doc("d3"), doc("d2")],
            [EvidenceRef(document_id="d1"), EvidenceRef(document_id="d2")],
            2,
            (1 + 0) / 2,
            [1, 0],
        ),
    ],
)
def test_context_precision_ap_table(retrieved, gold, k, expected_value, flags) -> None:
    result = context_precision_ap_at_k(retrieved, gold, k=k)

    assert result.metric_name == METRIC_CONTEXT_PRECISION_AP_AT_K
    assert result.status == "evaluated"
    assert result.value == pytest.approx(expected_value)
    assert result.details["mode"] == "average_precision"
    assert result.details["relevant_flags"] == flags


# --------------------------------------------------------------------------- 匹配规则


def test_chunk_level_gold_does_not_fall_back_to_document() -> None:
    """Gold 有 chunk_id 时，同文档其它 chunk 命中不算命中。"""
    gold = EvidenceRef(document_id="d1", chunk_id="c1")
    other_chunk = RetrievedItem(document_id="d1", chunk_id="c2")
    same_chunk = RetrievedItem(document_id="d1", chunk_id="c1")

    assert match_basis(gold, other_chunk) is None
    assert match_basis(gold, same_chunk) == "chunk_id"


def test_document_level_gold_matches_any_chunk_of_document() -> None:
    gold = EvidenceRef(document_id="d1")
    retrieved = RetrievedItem(document_id="d1", chunk_id="c99")

    assert match_basis(gold, retrieved) == "document_id"


def test_text_matching_requires_normalized_equality() -> None:
    gold = EvidenceRef(text="退款申请后 1-3 天到账。")

    exact = RetrievedItem(content="退款申请后1-3天到账")
    contained = RetrievedItem(content="退款申请后1-3天到账，请耐心等待")
    different = RetrievedItem(content="退款申请后7天到账")

    assert match_basis(gold, exact) == "text"
    assert match_basis(gold, contained) is None
    assert match_basis(gold, different) is None


def test_normalize_text_removes_case_space_and_punctuation() -> None:
    assert normalize_text("  Refund  1-3 Days，。 ") == "refund13days"


def test_duplicate_gold_is_deduped() -> None:
    gold = [EvidenceRef(document_id="d1"), EvidenceRef(document_id="d1")]
    result = context_recall([doc("d1")], gold)

    assert result.value == 1.0
    assert result.details["gold_count"] == 1


def test_duplicate_retrieved_keeps_first_rank() -> None:
    retrieved = [doc("d1"), doc("d1"), doc("d2")]
    result = mrr_at_k(retrieved, [EvidenceRef(document_id="d1")], k=3)

    assert result.details["first_relevant_rank"] == 1
    assert result.value == 1.0


def test_mixed_granularity_counts_each_gold_once() -> None:
    gold = [
        EvidenceRef(document_id="d1", chunk_id="c1"),
        EvidenceRef(document_id="d2"),
        EvidenceRef(text="发票在订单完成后 24 小时内开具"),
    ]
    retrieved = [
        RetrievedItem(document_id="d1", chunk_id="c9"),  # 不命中 chunk 级
        doc("d2"),  # 命中文档级
        RetrievedItem(content="发票在订单完成后24小时内开具"),  # 命中文本级
    ]

    recall = context_recall(retrieved, gold)
    hit = hit_rate_at_k(retrieved, gold, k=3)

    assert recall.value == pytest.approx(2 / 3)
    assert hit.value == 1.0


# --------------------------------------------------------------------------- 参数与聚合


def test_invalid_k_raises() -> None:
    with pytest.raises(ValueError):
        hit_rate_at_k([doc("d1")], [EvidenceRef(document_id="d1")], k=0)
    with pytest.raises(ValueError):
        context_precision_at_k([doc("d1")], [EvidenceRef(document_id="d1")], k=-1)


def test_evaluate_retrieval_emits_one_precision_variant() -> None:
    retrieved = [doc("d1")]
    gold = [EvidenceRef(document_id="d1")]

    at_k = evaluate_retrieval(retrieved, gold, k=5, precision_mode="at_k")
    ap = evaluate_retrieval(retrieved, gold, k=5, precision_mode="ap")

    assert set(at_k) == {
        METRIC_HIT_RATE,
        METRIC_MRR,
        METRIC_CONTEXT_RECALL,
        METRIC_CONTEXT_PRECISION_AT_K,
    }
    assert set(ap) == {
        METRIC_HIT_RATE,
        METRIC_MRR,
        METRIC_CONTEXT_RECALL,
        METRIC_CONTEXT_PRECISION_AP_AT_K,
    }
    with pytest.raises(ValueError):
        evaluate_retrieval(retrieved, gold, precision_mode="unknown")  # type: ignore[arg-type]


def test_failed_result_shape() -> None:
    result = failed_result(METRIC_HIT_RATE, "db down")

    assert result.status == "failed"
    assert result.value is None
    assert result.n_evaluated == 0
    assert result.details["error"] == "db down"
