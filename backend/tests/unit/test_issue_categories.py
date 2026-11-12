"""问题分类（#6）：Agent 兜底映射 + 批次对比的分类差值。"""
from __future__ import annotations

import uuid

from app.agents.evaluation_agent import QualityEvaluationAgent
from app.models import AnalysisResult, Task
from app.schemas.agents.evaluation import (
    DimensionScore,
    EvaluationLLMOutput,
    IssueItem,
)
from app.services.run_service import build_comparison


def _task() -> Task:
    return Task(id=uuid.uuid4(), task_type="evaluate", status="completed", result={})


def _row(score: float, categories: list[str]) -> AnalysisResult:
    return AnalysisResult(
        id=uuid.uuid4(),
        datasource_id=uuid.uuid4(),
        data_id=uuid.uuid4(),
        task_id=uuid.uuid4(),
        analysis_type="quality",
        result={
            "overall_score": score,
            "dimensions": {},
            "issue_items": [
                {"category": category, "dimension": "accuracy", "detail": f"{category} 示例"}
                for category in categories
            ],
        },
        agent_name="evaluation_agent",
    )


def test_issue_items_fall_back_to_dimension_category() -> None:
    llm_output = EvaluationLLMOutput(
        dimensions={
            "accuracy": DimensionScore(score=70, issues=["数字说错了"]),
            "completeness": DimensionScore(score=60, issues=["没答完"]),
            "hallucination": DimensionScore(score=80, issues=["knowledge_base_empty"]),
        },
        suggestions=[],
    )
    payload = {
        "accuracy": {"score": 70, "issues": ["数字说错了"]},
        "completeness": {"score": 60, "issues": ["没答完"]},
        "hallucination": {"score": 80, "issues": ["knowledge_base_empty"]},
    }

    items = QualityEvaluationAgent._collect_issue_items(  # noqa: SLF001
        llm_output, payload, ["accuracy", "completeness", "hallucination"]
    )
    categories = [item.category for item in items]

    assert categories == ["accuracy", "missing_knowledge", "missing_knowledge"]
    assert items[0].detail == "数字说错了"


def test_issue_items_prefer_model_categories() -> None:
    llm_output = EvaluationLLMOutput(
        dimensions={"accuracy": DimensionScore(score=70, issues=["数字说错了"])},
        suggestions=[],
        issue_items=[IssueItem(category="process", dimension="accuracy", detail="说错了且未转人工")],
    )
    payload = {"accuracy": {"score": 70, "issues": ["数字说错了"]}}

    items = QualityEvaluationAgent._collect_issue_items(  # noqa: SLF001
        llm_output, payload, ["accuracy"]
    )

    assert len(items) == 1
    assert items[0].category == "process"


def test_build_comparison_reports_category_deltas() -> None:
    base = _task()
    target = _task()
    base_rows = [_row(70, ["hallucination", "missing_knowledge"]), _row(60, ["missing_knowledge"])]
    target_rows = [_row(80, ["missing_knowledge"]), _row(65, ["tone"])]

    result = build_comparison(base, base_rows, target, target_rows)

    by_category = {item.category: item for item in result.categories}
    assert by_category["missing_knowledge"].base == 2
    assert by_category["missing_knowledge"].target == 1
    assert by_category["missing_knowledge"].delta == -1
    assert by_category["hallucination"].delta == -1
    assert by_category["tone"].target == 1
    assert by_category["missing_knowledge"].label == "知识缺失"
    # 分类按「总量」倒序
    assert result.categories[0].category == "missing_knowledge"


def test_build_comparison_with_legacy_rows_has_no_categories() -> None:
    base = _task()
    target = _task()
    legacy = AnalysisResult(
        id=uuid.uuid4(),
        datasource_id=uuid.uuid4(),
        data_id=uuid.uuid4(),
        analysis_type="quality",
        result={"overall_score": 70, "dimensions": {}, "needs_review": False},
        agent_name="evaluation_agent",
    )

    result = build_comparison(base, [legacy], target, [legacy])

    assert result.categories == []
