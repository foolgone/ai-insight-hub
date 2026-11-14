"""确定性检索指标（Phase 3A）。

纯函数：只依赖标准库，不访问数据库 / LLM / 网络 / 全局状态。

指标与口径（详见 ``docs/repair/04-evaluation-design.md``）：
- ``hit_rate``：Top-K 中是否至少命中一条 Gold Evidence；
- ``mrr``：第一个命中的排名倒数（未命中为 0）；
- ``context_recall``：命中的 Gold 条目数 / Gold 条目总数；
- ``context_precision_at_k``：Top-K 中相关的检索条目数 / 实际返回条目数；
- ``context_precision_ap_at_k``：AP@K（`(1/min(|G|,K))·Σ P@i·rel_i`）。

约定：
- Gold 粒度由字段决定且不可混用：有 ``chunk_id`` 只比 chunk；否则比 ``document_id``；
  否则按规范化文本**完全相等**（不做包含/相似度匹配）；
- ``skipped`` 的 ``value`` 为 ``None``，**不是 0**；
- 检索结果按 ``chunk_id → document_id → 规范化文本`` 去重，保留首次出现的排名。
"""
from __future__ import annotations

import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

MetricStatus = Literal["evaluated", "skipped", "failed"]
PrecisionMode = Literal["at_k", "ap"]

# 规范化文本时去掉的中英文标点（避免「。，」差异导致匹配失败）
_PUNCTUATION = frozenset("，。！？；：、“”‘’（）【】《》,.!?;:'\"()[]<>~`·…—-_/\\|")

SKIP_GOLD_MISSING = "gold_evidence_missing"
SKIP_NO_RETRIEVED = "no_retrieved_contexts"

METRIC_HIT_RATE = "hit_rate"
METRIC_MRR = "mrr"
METRIC_CONTEXT_RECALL = "context_recall"
METRIC_CONTEXT_PRECISION_AT_K = "context_precision_at_k"
METRIC_CONTEXT_PRECISION_AP_AT_K = "context_precision_ap_at_k"


@dataclass(frozen=True)
class EvidenceRef:
    """Gold Evidence（来自 ``qa_dataset_items.gold_evidence``）。"""

    document_id: str | None = None
    chunk_id: str | None = None
    text: str | None = None

    def level_key(self) -> tuple[str, str] | None:
        if self.chunk_id and self.chunk_id.strip():
            return ("chunk", self.chunk_id.strip())
        if self.document_id and self.document_id.strip():
            return ("document", self.document_id.strip())
        normalized = normalize_text(self.text or "")
        if normalized:
            return ("text", normalized)
        return None


@dataclass(frozen=True)
class RetrievedItem:
    """一条检索结果（来自 ``rag_traces.retrieved_contexts``）。"""

    content: str = ""
    document_id: str | None = None
    chunk_id: str | None = None
    rank: int | None = None

    def identity(self) -> tuple[str, str] | None:
        if self.chunk_id and self.chunk_id.strip():
            return ("chunk", self.chunk_id.strip())
        if self.document_id and self.document_id.strip():
            return ("document", self.document_id.strip())
        normalized = normalize_text(self.content)
        if normalized:
            return ("text", normalized)
        return None


@dataclass(frozen=True)
class MetricResult:
    """单样本指标结果（统一结构）。"""

    metric_name: str
    value: float | None
    status: MetricStatus = "evaluated"
    n_evaluated: int = 1
    n_skipped: int = 0
    skipped_reason: str | None = None
    details: Mapping[str, Any] = field(default_factory=dict)


# --------------------------------------------------------------------------- 基础工具


def normalize_text(text: str) -> str:
    """NFKC + casefold + 去空白 + 去标点（用于文本级证据的严格匹配）。"""
    normalized = unicodedata.normalize("NFKC", text or "").casefold()
    return "".join(char for char in normalized if not char.isspace() and char not in _PUNCTUATION)


def match_basis(gold: EvidenceRef, retrieved: RetrievedItem) -> str | None:
    """返回命中依据（``chunk_id`` / ``document_id`` / ``text``），未命中返回 None。

    粒度严格：Gold 有 ``chunk_id`` 时只接受同 ``chunk_id``，
    不会因为同文档其它 chunk 命中而算命中。
    """
    if gold.chunk_id and gold.chunk_id.strip():
        if retrieved.chunk_id and retrieved.chunk_id.strip() == gold.chunk_id.strip():
            return "chunk_id"
        return None
    if gold.document_id and gold.document_id.strip():
        if retrieved.document_id and retrieved.document_id.strip() == gold.document_id.strip():
            return "document_id"
        return None
    normalized_gold = normalize_text(gold.text or "")
    if normalized_gold and normalize_text(retrieved.content) == normalized_gold:
        return "text"
    return None


def _dedupe_gold(gold: Iterable[EvidenceRef]) -> list[EvidenceRef]:
    seen: set[tuple[str, str]] = set()
    result: list[EvidenceRef] = []
    for item in gold:
        key = item.level_key()
        if key is None or key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _dedupe_retrieved(
    retrieved: Iterable[RetrievedItem], *, k: int | None = None
) -> list[RetrievedItem]:
    ordered = sorted(
        enumerate(retrieved, start=1),
        key=lambda pair: (pair[1].rank if pair[1].rank is not None else pair[0]),
    )
    seen: set[tuple[str, str]] = set()
    result: list[RetrievedItem] = []
    for index, item in ordered:
        identity = item.identity()
        if identity is None or identity in seen:
            continue
        seen.add(identity)
        result.append(item)
    if k is not None:
        return result[:k]
    return result


def _check_k(k: int) -> None:
    if k <= 0:
        raise ValueError("k 必须为正整数")


def _skipped(
    metric_name: str, reason: str, *, details: Mapping[str, Any] | None = None
) -> MetricResult:
    return MetricResult(
        metric_name=metric_name,
        value=None,
        status="skipped",
        n_evaluated=0,
        n_skipped=1,
        skipped_reason=reason,
        details=dict(details or {}),
    )


def failed_result(metric_name: str, message: str) -> MetricResult:
    """运行期异常（数据库/外部错误）使用；指标函数本身不抛业务失败。"""
    return MetricResult(
        metric_name=metric_name,
        value=None,
        status="failed",
        n_evaluated=0,
        n_skipped=0,
        skipped_reason=None,
        details={"error": message},
    )


# --------------------------------------------------------------------------- 指标


def hit_rate_at_k(
    retrieved: Sequence[RetrievedItem], gold: Sequence[EvidenceRef], *, k: int = 5
) -> MetricResult:
    """Top-K 是否至少命中一条 Gold Evidence（1/0）。"""
    _check_k(k)
    gold_items = _dedupe_gold(gold)
    if not gold_items:
        return _skipped(METRIC_HIT_RATE, SKIP_GOLD_MISSING, details={"k": k})

    items = _dedupe_retrieved(retrieved, k=k)
    for position, item in enumerate(items, start=1):
        for gold_item in gold_items:
            if match_basis(gold_item, item):
                return MetricResult(
                    metric_name=METRIC_HIT_RATE,
                    value=1.0,
                    details={"k": k, "first_match_rank": position},
                )
    return MetricResult(
        metric_name=METRIC_HIT_RATE,
        value=0.0,
        details={"k": k, "first_match_rank": None, "returned_count": len(items)},
    )


def mrr_at_k(
    retrieved: Sequence[RetrievedItem], gold: Sequence[EvidenceRef], *, k: int = 5
) -> MetricResult:
    """第一个命中的排名倒数；未命中为 0。"""
    _check_k(k)
    gold_items = _dedupe_gold(gold)
    if not gold_items:
        return _skipped(METRIC_MRR, SKIP_GOLD_MISSING, details={"k": k})

    items = _dedupe_retrieved(retrieved, k=k)
    for position, item in enumerate(items, start=1):
        if any(match_basis(gold_item, item) for gold_item in gold_items):
            return MetricResult(
                metric_name=METRIC_MRR,
                value=round(1.0 / position, 6),
                details={"k": k, "first_relevant_rank": position},
            )
    return MetricResult(
        metric_name=METRIC_MRR,
        value=0.0,
        details={"k": k, "first_relevant_rank": None, "returned_count": len(items)},
    )


def context_recall(retrieved: Sequence[RetrievedItem], gold: Sequence[EvidenceRef]) -> MetricResult:
    """命中的 Gold 条目数 / Gold 条目总数（Gold 为空 → skipped）。"""
    gold_items = _dedupe_gold(gold)
    if not gold_items:
        return _skipped(METRIC_CONTEXT_RECALL, SKIP_GOLD_MISSING)

    items = _dedupe_retrieved(retrieved)
    matched: list[dict[str, Any]] = []
    unmatched: list[int] = []
    for index, gold_item in enumerate(gold_items):
        basis = next((basis for item in items if (basis := match_basis(gold_item, item))), None)
        if basis is None:
            unmatched.append(index)
        else:
            matched.append(
                {
                    "gold_index": index,
                    "basis": basis,
                    "gold": {
                        "document_id": gold_item.document_id,
                        "chunk_id": gold_item.chunk_id,
                    },
                }
            )

    return MetricResult(
        metric_name=METRIC_CONTEXT_RECALL,
        value=round(len(matched) / len(gold_items), 6),
        details={
            "gold_count": len(gold_items),
            "matched_count": len(matched),
            "matched": matched,
            "unmatched_indices": unmatched,
            "returned_count": len(items),
        },
    )


def context_precision_at_k(
    retrieved: Sequence[RetrievedItem], gold: Sequence[EvidenceRef], *, k: int = 5
) -> MetricResult:
    """Precision@K：Top-K 中相关条目数 / 实际返回条目数（不考虑位置权重）。"""
    _check_k(k)
    gold_items = _dedupe_gold(gold)
    if not gold_items:
        return _skipped(METRIC_CONTEXT_PRECISION_AT_K, SKIP_GOLD_MISSING, details={"k": k})

    items = _dedupe_retrieved(retrieved, k=k)
    if not items:
        return _skipped(
            METRIC_CONTEXT_PRECISION_AT_K,
            SKIP_NO_RETRIEVED,
            details={"k": k, "returned_count": 0},
        )

    relevant_positions = [
        position
        for position, item in enumerate(items, start=1)
        if any(match_basis(gold_item, item) for gold_item in gold_items)
    ]
    return MetricResult(
        metric_name=METRIC_CONTEXT_PRECISION_AT_K,
        value=round(len(relevant_positions) / len(items), 6),
        details={
            "k": k,
            "mode": "precision_at_k",
            "returned_count": len(items),
            "relevant_count": len(relevant_positions),
            "relevant_positions": relevant_positions,
        },
    )


def context_precision_ap_at_k(
    retrieved: Sequence[RetrievedItem], gold: Sequence[EvidenceRef], *, k: int = 5
) -> MetricResult:
    """AP@K：`(1/min(|G|,K)) · Σ P@i · rel_i`（考虑排名）。"""
    _check_k(k)
    gold_items = _dedupe_gold(gold)
    if not gold_items:
        return _skipped(METRIC_CONTEXT_PRECISION_AP_AT_K, SKIP_GOLD_MISSING, details={"k": k})

    items = _dedupe_retrieved(retrieved, k=k)
    if not items:
        return _skipped(
            METRIC_CONTEXT_PRECISION_AP_AT_K,
            SKIP_NO_RETRIEVED,
            details={"k": k, "returned_count": 0},
        )

    relevant_flags: list[int] = []
    precision_at_each_rank: list[float] = []
    hits = 0
    for position, item in enumerate(items, start=1):
        relevant = any(match_basis(gold_item, item) for gold_item in gold_items)
        flag = 1 if relevant else 0
        relevant_flags.append(flag)
        hits += flag
        precision_at_each_rank.append(round(hits / position, 6))

    denominator = min(len(gold_items), k)
    value = (
        sum(precision * flag for precision, flag in zip(precision_at_each_rank, relevant_flags))
        / denominator
        if denominator
        else 0.0
    )
    return MetricResult(
        metric_name=METRIC_CONTEXT_PRECISION_AP_AT_K,
        value=round(value, 6),
        details={
            "k": k,
            "mode": "average_precision",
            "returned_count": len(items),
            "gold_count": len(gold_items),
            "relevant_flags": relevant_flags,
            "precision_at_each_rank": precision_at_each_rank,
        },
    )


def evaluate_retrieval(
    retrieved: Sequence[RetrievedItem],
    gold: Sequence[EvidenceRef],
    *,
    k: int = 5,
    precision_mode: PrecisionMode = "at_k",
) -> dict[str, MetricResult]:
    """一次算齐检索指标（3C 批量任务用）。

    ``precision_mode`` 决定使用 ``context_precision_at_k`` 还是 ``context_precision_ap_at_k``，
    两者不会同时产出，避免聚合时口径混淆。
    """
    if precision_mode not in ("at_k", "ap"):
        raise ValueError("precision_mode 必须是 'at_k' 或 'ap'")

    results = {
        METRIC_HIT_RATE: hit_rate_at_k(retrieved, gold, k=k),
        METRIC_MRR: mrr_at_k(retrieved, gold, k=k),
        METRIC_CONTEXT_RECALL: context_recall(retrieved, gold),
    }
    if precision_mode == "at_k":
        results[METRIC_CONTEXT_PRECISION_AT_K] = context_precision_at_k(retrieved, gold, k=k)
    else:
        results[METRIC_CONTEXT_PRECISION_AP_AT_K] = context_precision_ap_at_k(retrieved, gold, k=k)
    return results


__all__ = [
    "EvidenceRef",
    "METRIC_CONTEXT_PRECISION_AP_AT_K",
    "METRIC_CONTEXT_PRECISION_AT_K",
    "METRIC_CONTEXT_RECALL",
    "METRIC_HIT_RATE",
    "METRIC_MRR",
    "MetricResult",
    "PrecisionMode",
    "RetrievedItem",
    "SKIP_GOLD_MISSING",
    "SKIP_NO_RETRIEVED",
    "context_precision_ap_at_k",
    "context_precision_at_k",
    "context_recall",
    "evaluate_retrieval",
    "failed_result",
    "hit_rate_at_k",
    "match_basis",
    "mrr_at_k",
    "normalize_text",
]
