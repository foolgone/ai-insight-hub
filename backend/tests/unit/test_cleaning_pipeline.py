"""清洗流水线纯函数测试：近似重复标记、状态机、清洗输入取值。

覆盖 2026-11-05 的两处修复：
1. 近似重复去重（``dedup_threshold``）真正接入流水线；
2. 6 态清洗状态机真正驱动并校验跳转。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.schemas.agents.cleaning import CleaningState
from app.services.cleaning_service import (
    NEAR_DUP_MAX_ITEMS,
    _advance_state,
    _current_state,
    _mark_near_duplicates,
    _raw_text,
)

pytestmark = pytest.mark.unit


def _task(current_step: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(current_step=current_step)


def _dialogue(user: str, ai: str, **extra: object) -> dict:
    return {
        "user_message": user,
        "ai_response": ai,
        "quality_score": 90.0,
        "issues": [],
        **extra,
    }


# --------------------------------------------------------------------------- 近似重复


def test_mark_near_duplicates_keeps_records_and_tags_later_one() -> None:
    dialogues = [
        _dialogue("你们什么时候发货", "48 小时内发出"),
        _dialogue("你们什么时候发货？", "48 小时内发出"),  # 仅差标点，相似度很高
        _dialogue("能开发票吗", "可以开专票"),
    ]

    marked = _mark_near_duplicates(dialogues, threshold=0.9)

    assert marked == 1
    assert len(dialogues) == 3  # 只打标，不删数据
    assert dialogues[1]["issues"] == ["duplicate"]
    assert dialogues[0]["issues"] == []
    assert dialogues[2]["issues"] == []


def test_mark_near_duplicates_respects_threshold() -> None:
    dialogues = [
        _dialogue("发货要多久", "48 小时"),
        _dialogue("退款要多久", "3 个工作日"),
    ]

    assert _mark_near_duplicates(dialogues, threshold=0.95) == 0
    assert all(item["issues"] == [] for item in dialogues)


def test_mark_near_duplicates_does_not_duplicate_existing_tag() -> None:
    dialogues = [
        _dialogue("你好", "您好"),
        _dialogue("你好", "您好", issues=["duplicate"]),
    ]

    marked = _mark_near_duplicates(dialogues, threshold=0.9)

    assert marked == 0
    assert dialogues[1]["issues"] == ["duplicate"]


def test_mark_near_duplicates_skips_oversized_batch() -> None:
    dialogues = [_dialogue(f"问题{i}", f"回答{i}") for i in range(NEAR_DUP_MAX_ITEMS + 1)]

    assert _mark_near_duplicates(dialogues, threshold=0.95) == 0


# --------------------------------------------------------------------------- 状态机


def test_state_machine_happy_path_across_two_records() -> None:
    task = _task("pending")

    for state, detail in [
        (CleaningState.PARSING, "loading raw data"),
        (CleaningState.NORMALIZING, "1/2"),
        (CleaningState.DEDUPLICATING, "1/2"),
        (CleaningState.VALIDATING, "1/2"),
        (CleaningState.NORMALIZING, "2/2"),
        (CleaningState.DEDUPLICATING, "2/2"),
        (CleaningState.VALIDATING, "2/2"),
        (CleaningState.COMPLETED, None),
    ]:
        _advance_state(task, state, detail=detail)

    assert task.current_step == "completed"


def test_state_machine_rejects_illegal_transition() -> None:
    task = _task("pending")

    with pytest.raises(ValueError, match="illegal cleaning state transition"):
        _advance_state(task, CleaningState.COMPLETED)


def test_state_machine_allows_failed_record_then_next_record() -> None:
    """某条记录清洗失败时走 VALIDATING，下一条仍能回到 NORMALIZING。"""
    task = _task("pending")
    _advance_state(task, CleaningState.PARSING, detail="loading raw data")
    _advance_state(task, CleaningState.NORMALIZING, detail="1/2")
    _advance_state(task, CleaningState.VALIDATING, detail="1/2")  # 第 1 条失败
    _advance_state(task, CleaningState.NORMALIZING, detail="2/2")
    _advance_state(task, CleaningState.DEDUPLICATING, detail="2/2")
    _advance_state(task, CleaningState.VALIDATING, detail="2/2")
    _advance_state(task, CleaningState.COMPLETED)

    assert task.current_step == "completed"


def test_state_machine_allows_failure_from_any_active_state() -> None:
    task = _task("deduplicating 1/1")

    _advance_state(task, CleaningState.FAILED)

    assert task.current_step == "failed"


def test_current_state_parses_detail_suffix_and_legacy_values() -> None:
    assert _current_state(_task("validating 3/10")) is CleaningState.VALIDATING
    assert _current_state(_task("normalizing")) is CleaningState.NORMALIZING
    assert _current_state(_task("loading_raw_data")) is None
    assert _current_state(_task(None)) is None


# --------------------------------------------------------------------------- 清洗输入取值


def test_raw_text_prefers_text_then_records_then_metadata() -> None:
    text_raw = SimpleNamespace(raw_content={"text": "user_message,ai_response", "format": "csv"})
    assert _raw_text(text_raw) == "user_message,ai_response"

    records_raw = SimpleNamespace(
        raw_content={"text": "", "format": "xlsx", "records": [{"user_message": "你好"}]}
    )
    assert '"user_message": "你好"' in _raw_text(records_raw)

    meta_raw = SimpleNamespace(raw_content={"text": "", "format": "xlsx", "record_count": 0})
    assert "xlsx" in _raw_text(meta_raw)
