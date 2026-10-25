"""B-501 冷启动状态与工作流推进测试。"""
from __future__ import annotations

import pytest

from app.services.knowledge_status import (
    READY_THRESHOLD,
    KnowledgeStage,
    stage_for_count,
)
from app.services.onboarding_service import (
    WORKFLOW_STATUSES,
    knowledge_built_status_for,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("count", "expected"),
    [
        (0, KnowledgeStage.COLD),
        (-1, KnowledgeStage.COLD),
        (1, KnowledgeStage.WARMING),
        (10, KnowledgeStage.WARMING),
        (49, KnowledgeStage.WARMING),
        (READY_THRESHOLD, KnowledgeStage.READY),
        (500, KnowledgeStage.READY),
    ],
)
def test_stage_for_count(count: int, expected: KnowledgeStage) -> None:
    assert stage_for_count(count) is expected


def test_ready_threshold_is_50() -> None:
    assert READY_THRESHOLD == 50


def test_workflow_status_sequence() -> None:
    assert WORKFLOW_STATUSES == (
        "created",
        "data_uploaded",
        "data_cleaned",
        "knowledge_built",
        "ready",
    )


@pytest.mark.parametrize(
    ("total", "expected"),
    [
        (0, "data_cleaned"),
        (1, "knowledge_built"),
        (49, "knowledge_built"),
        (50, "ready"),
    ],
)
def test_knowledge_built_status_for(total: int, expected: str) -> None:
    assert knowledge_built_status_for(total) == expected
