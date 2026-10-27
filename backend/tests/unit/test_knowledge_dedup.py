"""T9 Phase 1：知识提取对话去重 / 既有问题语义选优单测。"""
from __future__ import annotations

import uuid

import pytest

from app.services import embedding_service, knowledge_dedup
from app.services.knowledge_dedup import (
    dedupe_dialogues,
    dialogue_query_text,
    estimate_prompt_savings,
    expand_source_ids,
    normalize_text,
    select_relevant_questions,
)

pytestmark = pytest.mark.unit


def _dialogue(dialogue_id: str, question: str, answer: str = "标准答案") -> dict:
    return {
        "dialogue_id": dialogue_id,
        "user_message": question,
        "ai_response": answer,
    }


class TestNormalizeText:
    def test_normalizes_case_width_and_whitespace(self) -> None:
        assert normalize_text("  How  Much？ ") == normalize_text("how much")
        assert normalize_text("退款　多久到账。") == "退款 多久到账"

    def test_empty_input(self) -> None:
        assert normalize_text("") == ""
        assert normalize_text(None) == ""  # type: ignore[arg-type]


class TestDedupeDialogues:
    def test_merges_exact_pairs_and_counts(self) -> None:
        dialogues = [
            _dialogue("d1", "怎么退款？"),
            _dialogue("d2", "怎么退款"),
            _dialogue("d3", "怎么退款？"),
            _dialogue("d4", "多久发货"),
        ]

        deduped, removed, id_map = dedupe_dialogues(dialogues)

        assert removed == 2
        assert [item["dialogue_id"] for item in deduped] == ["d1", "d4"]
        assert deduped[0]["duplicate_count"] == 3
        assert deduped[1]["duplicate_count"] == 1
        assert id_map["d1"] == ["d1", "d2", "d3"]

    def test_same_question_different_answer_not_merged(self) -> None:
        dialogues = [
            _dialogue("d1", "怎么退款？", "7 天可退"),
            _dialogue("d2", "怎么退款！", "15 天可退"),
        ]

        deduped, removed, _ = dedupe_dialogues(dialogues)

        assert removed == 0
        assert len(deduped) == 2

    def test_preserves_order_and_first_occurrence(self) -> None:
        dialogues = [_dialogue("b", "问题"), _dialogue("a", "问题")]

        deduped, _, id_map = dedupe_dialogues(dialogues)

        assert [item["dialogue_id"] for item in deduped] == ["b"]
        assert id_map == {"b": ["b", "a"]}

    def test_empty_and_missing_ids(self) -> None:
        assert dedupe_dialogues([]) == ([], 0, {})

        deduped, removed, id_map = dedupe_dialogues(
            [{"user_message": "q", "ai_response": "a"}, {"user_message": "q", "ai_response": "a"}]
        )
        assert removed == 1
        assert len(deduped) == 1
        assert id_map == {}


class TestExpandSourceIds:
    def test_expands_representative_to_cluster(self) -> None:
        faqs = [{"source_dialogue_ids": ["d1"]}]

        expanded = expand_source_ids(faqs, {"d1": ["d1", "d2", "d3"]})

        assert expanded == 1
        assert faqs[0]["source_dialogue_ids"] == ["d1", "d2", "d3"]

    def test_unchanged_without_mapping(self) -> None:
        faqs = [{"source_dialogue_ids": ["d9"]}]

        assert expand_source_ids(faqs, {}) == 0
        assert faqs[0]["source_dialogue_ids"] == ["d9"]


class TestQueryTextAndEstimates:
    def test_query_text_truncated(self) -> None:
        dialogues = [_dialogue("d1", "问题一"), _dialogue("d2", "问题二")]

        assert dialogue_query_text(dialogues, max_chars=100) == "问题一 问题二"
        assert len(dialogue_query_text(dialogues, max_chars=3)) == 3

    def test_savings_non_negative(self) -> None:
        deduped = [_dialogue("d1", "怎么退款", "7 天可退")]
        chars, tokens = estimate_prompt_savings(
            deduped_dialogues=deduped,
            removed_dialogues=2,
            legacy_questions=[f"既有问题 {i}" for i in range(30)],
            sent_questions=["既有问题 1"],
        )

        assert chars > 0
        assert tokens == int(chars / 1.6)


class TestSelectRelevantQuestionsFallback:
    async def test_top_k_zero_returns_legacy(self) -> None:
        questions, mode, reason = await select_relevant_questions(
            None,
            datasource_id=uuid.uuid4(),
            dialogues=[_dialogue("d1", "问题")],
            legacy_questions=["a", "b"],
            top_k=0,
        )

        assert questions == ["a", "b"]
        assert mode == "legacy_top30"
        assert reason is None

    async def test_no_legacy_questions(self) -> None:
        questions, mode, reason = await select_relevant_questions(
            None,
            datasource_id=uuid.uuid4(),
            dialogues=[_dialogue("d1", "问题")],
            legacy_questions=[],
            top_k=8,
        )

        assert questions == []
        assert mode == "embedding_topk"
        assert reason is None

    async def test_embedding_failure_falls_back(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def _boom(texts: list[str]) -> list[list[float]]:
            raise RuntimeError("model unavailable")

        monkeypatch.setattr(embedding_service, "encode_texts", _boom)

        questions, mode, reason = await select_relevant_questions(
            object(),  # type: ignore[arg-type] - embedding 先失败，不会用到 session
            datasource_id=uuid.uuid4(),
            dialogues=[_dialogue("d1", "问题")],
            legacy_questions=["a", "b"],
            top_k=8,
        )

        assert questions == ["a", "b"]
        assert mode == "fallback"
        assert reason is not None and "RuntimeError" in reason


def test_module_exports() -> None:
    assert knowledge_dedup.__all__
