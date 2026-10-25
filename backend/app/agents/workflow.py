"""自研工作流编排器（B-604；ADR-001，无框架依赖，≤150 行）。

固定 6 步：clean → evaluate →（needs_review? manual_review）→ extract → insight → report。
- 单步失败不抛穿：错误记入 ``state.errors``；可继续的步骤继续（洞察失败仅降级）；
- clean 失败（无数据）直接终止；人工复核置 ``awaiting_review``，``resume`` 可回主链；
- 默认步骤适配器在 ``workflow_steps.py``；Agent 均可注入替身（测试）。
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

StepFunc = Callable[["WorkflowState"], Awaitable[dict[str, Any] | None]]
REVIEW_THRESHOLD = 70.0


@dataclass
class WorkflowState:
    datasource_id: str
    raw_data: str = ""
    cleaned_data: list[dict[str, Any]] = field(default_factory=list)
    evaluation_results: list[dict[str, Any]] = field(default_factory=list)
    knowledge_base: list[dict[str, Any]] = field(default_factory=list)
    knowledge_gaps: list[dict[str, Any]] = field(default_factory=list)
    insights: dict[str, Any] | None = None
    report: dict[str, Any] | None = None
    manual_review_required: bool = False
    status: str = "pending"
    errors: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)

    def apply(self, payload: dict[str, Any] | None) -> None:
        for key, value in (payload or {}).items():
            setattr(self, key, value)


def needs_manual_review(results: list[dict[str, Any]]) -> bool:
    return any(
        float(item.get("overall_score", 100)) < REVIEW_THRESHOLD or bool(item.get("needs_review"))
        for item in results
    )


class WorkflowOrchestrator:
    """框架无关的顺序编排器（条件分支：人工复核）。"""

    def __init__(self, *, steps: dict[str, StepFunc] | None = None, **agent_kwargs: Any) -> None:
        if steps is None:
            from app.agents.workflow_steps import build_default_steps

            steps = build_default_steps(**agent_kwargs)
        self._steps = steps

    async def run(self, datasource_id: str, raw_data: str) -> WorkflowState:
        state = WorkflowState(datasource_id=datasource_id, raw_data=raw_data)
        if not await self._run("clean", state):
            state.status = "failed"
            return state
        await self._run("evaluate", state)
        if needs_manual_review(state.evaluation_results):
            state.manual_review_required = True
            state.status = "awaiting_review"
            state.steps.append("manual_review")
            return state
        return await self._continue(state)

    async def resume(self, state: WorkflowState, *, approved: bool = True) -> WorkflowState:
        if state.status != "awaiting_review":
            raise ValueError(f"workflow is not awaiting review: {state.status}")
        state.manual_review_required = False
        state.steps.append("resume")
        if not approved:
            state.status = "rejected"
            return state
        state.status = "reviewed"
        return await self._continue(state)

    async def _continue(self, state: WorkflowState) -> WorkflowState:
        await self._run("extract", state)
        await self._run("insight", state)  # 洞察失败仅降级，不阻塞报告
        await self._run("report", state)
        state.status = "completed" if state.report else "failed"
        return state

    async def _run(self, name: str, state: WorkflowState) -> bool:
        state.steps.append(name)
        try:
            state.apply(await self._steps[name](state))
            return True
        except Exception as exc:  # noqa: BLE001 - 单步失败不中断
            state.errors.append(f"{name}: {exc}")
            return False


__all__ = [
    "REVIEW_THRESHOLD",
    "StepFunc",
    "WorkflowOrchestrator",
    "WorkflowState",
    "needs_manual_review",
]
