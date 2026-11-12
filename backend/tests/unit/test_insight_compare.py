"""洞察批次对比（#3）：情感/意图差值 + 痛点增减。"""
from __future__ import annotations

import uuid

from app.models import Task
from app.services.run_service import build_insight_comparison


def _task(payload: dict) -> Task:
    return Task(
        id=uuid.uuid4(),
        task_type="analyze",
        status="completed",
        result={"evaluated": 0},
    )


BASE = {
    "sentiment_distribution": {"正面": 0.3, "中性": 0.5, "负面": 0.2},
    "intent_distribution": {"退款": 10, "物流": 4, "发票": 2},
    "pain_points": [
        {"pain_point": "退款到账慢"},
        {"pain_point": "物流更新不及时"},
    ],
}

TARGET = {
    "sentiment_distribution": {"正面": 0.5, "中性": 0.4, "负面": 0.1},
    "intent_distribution": {"退款": 6, "物流": 9, "发票": 2},
    "pain_points": [
        {"pain_point": "退款到账慢"},
        {"pain_point": "发票开具流程复杂"},
    ],
}


def test_insight_comparison_reports_metric_deltas() -> None:
    result = build_insight_comparison(_task(BASE), BASE, _task(TARGET), TARGET)

    sentiment = {item.name: item for item in result.sentiment}
    assert sentiment["负面"].base == 0.2
    assert sentiment["负面"].target == 0.1
    assert sentiment["负面"].delta == -0.1

    intents = {item.name: item for item in result.intents}
    assert intents["物流"].delta == 5
    assert intents["退款"].delta == -4
    # 意图按两侧总量倒序
    assert result.intents[0].name in {"退款", "物流"}


def test_insight_comparison_reports_pain_point_changes() -> None:
    result = build_insight_comparison(_task(BASE), BASE, _task(TARGET), TARGET)

    assert result.pain_points_added == ["发票开具流程复杂"]
    assert result.pain_points_removed == ["物流更新不及时"]


def test_insight_comparison_handles_plain_string_pain_points() -> None:
    base = {"pain_points": ["退款慢"], "sentiment_distribution": {}, "intent_distribution": {}}
    target = {
        "pain_points": ["退款慢", "发票慢"],
        "sentiment_distribution": {},
        "intent_distribution": {},
    }

    result = build_insight_comparison(_task(base), base, _task(target), target)

    assert result.pain_points_added == ["发票慢"]
    assert result.pain_points_removed == []
