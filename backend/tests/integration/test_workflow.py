"""B-605 工作流编排器集成测试（主链/复核分支/失败节点）。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.agents.base import AgentResult
from app.agents.workflow import (
    REVIEW_THRESHOLD,
    WorkflowOrchestrator,
    needs_manual_review,
)

pytestmark = pytest.mark.integration


def _steps(**overrides: Any) -> dict[str, Any]:
    async def clean(state) -> dict[str, Any]:  # noqa: ANN001
        return {
            "cleaned_data": [
                {
                    "dialogue_id": "d-1",
                    "user_message": "怎么退货",
                    "ai_response": "在订单页申请",
                }
            ]
        }

    async def evaluate(state) -> dict[str, Any]:  # noqa: ANN001
        return {"evaluation_results": [{"overall_score": 95.0, "needs_review": False}]}

    async def extract(state) -> dict[str, Any]:  # noqa: ANN001
        return {
            "knowledge_base": [{"question": "怎么退货？", "answer": "订单页申请"}],
            "knowledge_gaps": [],
        }

    async def insight(state) -> dict[str, Any]:  # noqa: ANN001
        return {"insights": {"intent_distribution": {"咨询": 1}}}

    async def report(state) -> dict[str, Any]:  # noqa: ANN001
        return {"report": {"sections": [{"title": "概览", "content": "ok"}]}}

    steps = {
        "clean": clean,
        "evaluate": evaluate,
        "extract": extract,
        "insight": insight,
        "report": report,
    }
    steps.update(overrides)
    return steps


def test_needs_manual_review_threshold() -> None:
    assert REVIEW_THRESHOLD == 70.0
    assert needs_manual_review([{"overall_score": 70.0}]) is False
    assert needs_manual_review([{"overall_score": 69.9}]) is True
    assert needs_manual_review([{"needs_review": True, "overall_score": 90}]) is True
    assert needs_manual_review([]) is False


def test_workflow_has_no_framework_dependency() -> None:
    source = Path("app/agents/workflow.py").read_text(encoding="utf-8")
    assert "langchain" not in source.lower()
    assert "langgraph" not in source.lower()


def test_orchestrator_file_under_150_lines() -> None:
    lines = Path("app/agents/workflow.py").read_text(encoding="utf-8").splitlines()
    assert len(lines) <= 150, f"workflow.py has {len(lines)} lines"


async def test_main_chain_runs_in_order() -> None:
    orchestrator = WorkflowOrchestrator(steps=_steps())

    state = await orchestrator.run("ds-1", "客户：怎么退货 客服：订单页申请")

    assert state.status == "completed"
    assert state.steps == ["clean", "evaluate", "extract", "insight", "report"]
    assert state.cleaned_data
    assert state.evaluation_results[0]["overall_score"] == 95.0
    assert state.knowledge_base
    assert state.insights is not None
    assert state.report is not None
    assert state.errors == []


async def test_low_score_goes_to_manual_review_and_resumes() -> None:
    async def low_evaluate(state) -> dict[str, Any]:  # noqa: ANN001
        return {"evaluation_results": [{"overall_score": 55.0, "needs_review": True}]}

    orchestrator = WorkflowOrchestrator(steps=_steps(evaluate=low_evaluate))

    state = await orchestrator.run("ds-1", "raw")

    assert state.status == "awaiting_review"
    assert state.manual_review_required is True
    assert state.steps == ["clean", "evaluate", "manual_review"]
    assert state.report is None

    resumed = await orchestrator.resume(state)

    assert resumed.status == "completed"
    assert resumed.manual_review_required is False
    assert resumed.steps[-1] == "report"
    assert resumed.report is not None


async def test_resume_rejects_wrong_state() -> None:
    orchestrator = WorkflowOrchestrator(steps=_steps())
    state = await orchestrator.run("ds-1", "raw")

    with pytest.raises(ValueError):
        await orchestrator.resume(state)


async def test_insight_failure_degrades_without_blocking_report() -> None:
    async def broken_insight(state) -> dict[str, Any]:  # noqa: ANN001
        raise RuntimeError("insight boom")

    orchestrator = WorkflowOrchestrator(steps=_steps(insight=broken_insight))

    state = await orchestrator.run("ds-1", "raw")

    assert state.status == "completed"
    assert state.insights is None
    assert state.report is not None
    assert any("insight: insight boom" in item for item in state.errors)


async def test_extract_failure_does_not_crash_workflow() -> None:
    async def broken_extract(state) -> dict[str, Any]:  # noqa: ANN001
        raise RuntimeError("extract boom")

    orchestrator = WorkflowOrchestrator(steps=_steps(extract=broken_extract))

    state = await orchestrator.run("ds-1", "raw")

    assert state.status == "completed"
    assert state.errors
    assert state.report is not None


async def test_clean_failure_stops_workflow() -> None:
    async def broken_clean(state) -> dict[str, Any]:  # noqa: ANN001
        raise RuntimeError("clean boom")

    orchestrator = WorkflowOrchestrator(steps=_steps(clean=broken_clean))

    state = await orchestrator.run("ds-1", "raw")

    assert state.status == "failed"
    assert state.steps == ["clean"]
    assert state.report is None


async def test_report_failure_marks_failed() -> None:
    async def broken_report(state) -> dict[str, Any]:  # noqa: ANN001
        raise RuntimeError("report boom")

    orchestrator = WorkflowOrchestrator(steps=_steps(report=broken_report))

    state = await orchestrator.run("ds-1", "raw")

    assert state.status == "failed"
    assert any("report: report boom" in item for item in state.errors)


async def test_rejected_review_does_not_continue() -> None:
    async def low_evaluate(state) -> dict[str, Any]:  # noqa: ANN001
        return {"evaluation_results": [{"overall_score": 50.0}]}

    orchestrator = WorkflowOrchestrator(steps=_steps(evaluate=low_evaluate))
    state = await orchestrator.run("ds-1", "raw")

    rejected = await orchestrator.resume(state, approved=False)

    assert rejected.status == "rejected"
    assert rejected.report is None


class _StubAgent:
    """默认步骤适配器测试用的 Agent 替身。"""

    def __init__(self, result: AgentResult) -> None:
        self._result = result
        self.calls: list[dict[str, Any]] = []

    async def _call(self, payload: dict[str, Any], **kwargs: Any) -> AgentResult:
        self.calls.append(payload)
        return self._result


class _CleanStub(_StubAgent):
    async def clean(self, payload: dict[str, Any], **kwargs: Any) -> AgentResult:
        return await self._call(payload, **kwargs)


class _EvaluateStub(_StubAgent):
    async def evaluate(self, payload: dict[str, Any], **kwargs: Any) -> AgentResult:
        return await self._call(payload, **kwargs)


class _ExtractStub(_StubAgent):
    async def extract(self, payload: dict[str, Any], **kwargs: Any) -> AgentResult:
        return await self._call(payload, **kwargs)


class _InsightStub(_StubAgent):
    async def analyze(self, payload: dict[str, Any], **kwargs: Any) -> AgentResult:
        return await self._call(payload, **kwargs)


class _ReportStub(_StubAgent):
    async def generate(self, payload: dict[str, Any], **kwargs: Any) -> AgentResult:
        return await self._call(payload, **kwargs)


async def test_default_steps_adapters_wire_agents() -> None:
    from app.agents.workflow_steps import build_default_steps

    dialogue = {"dialogue_id": "d-1", "user_message": "q", "ai_response": "a"}
    clean_agent = _CleanStub(AgentResult(success=True, data={"dialogues": [dialogue]}))
    evaluate_agent = _EvaluateStub(
        AgentResult(
            success=True,
            data={"overall_score": 95.0, "needs_review": False},
        )
    )
    extract_agent = _ExtractStub(
        AgentResult(
            success=True,
            data={"faqs": [{"question": "q", "answer": "a"}], "gaps": []},
        )
    )
    insight_agent = _InsightStub(AgentResult(success=True, data={"intent_distribution": {"咨询": 1}}))
    report_agent = _ReportStub(
        AgentResult(success=True, data={"sections": [{"title": "t", "content": "c"}]})
    )

    steps = build_default_steps(
        session=None,
        cleaning_agent=clean_agent,
        evaluation_agent=evaluate_agent,
        extraction_agent=extract_agent,
        insight_agent=insight_agent,
        report_agent=report_agent,
    )
    orchestrator = WorkflowOrchestrator(steps=steps)

    state = await orchestrator.run("ds-1", "raw text")

    assert state.status == "completed"
    assert state.knowledge_base == [{"question": "q", "answer": "a"}]
    assert state.insights == {"intent_distribution": {"咨询": 1}}
    assert state.report is not None
    assert clean_agent.calls[0]["raw_data"] == "raw text"
    assert evaluate_agent.calls[0]["dialogue"] == dialogue
    assert report_agent.calls[0]["report_type"] == "comprehensive"
    assert report_agent.calls[0]["data"]["quality_summary"]["avg_score"] == 95.0
