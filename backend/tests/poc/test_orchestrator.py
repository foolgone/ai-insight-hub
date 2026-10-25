"""B-103：自研编排器原型（替代 LangGraph）——6 步 + 条件分支 + 失败不中断。

原型只验证编排语义，不代表 B-604 的最终实现（后者在 P6 与真实 Agent 接线）。
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import pytest

pytestmark = pytest.mark.slow

State = dict[str, Any]
Node = Callable[[State], Awaitable[State]]


async def _clean(state: State) -> State:
    state["cleaned_data"] = [{"id": 1, "quality_score": state.get("seed_score", 85)}]
    state["steps"].append("clean")
    return state


async def _evaluate(state: State) -> State:
    score = state["cleaned_data"][0]["quality_score"]
    state["evaluation_results"] = [{"overall_score": score}]
    state["needs_review"] = score < 70
    state["steps"].append("evaluate")
    return state


async def _manual_review(state: State) -> State:
    state["manual_review_result"] = {"reviewer": "human", "decision": "approved"}
    state["steps"].append("manual_review")
    return state


async def _extract(state: State) -> State:
    state["faq"] = [{"question": "iPhone 14 多少钱", "answer": "5999 元起"}]
    state["steps"].append("extract")
    return state


async def _insight(state: State) -> State:
    if state.get("fail_insight"):
        raise RuntimeError("洞察服务不可用")
    state["insights"] = {"sentiment": {"positive": 0.8}}
    state["steps"].append("insight")
    return state


async def _report(state: State) -> State:
    state["report"] = {"status": "completed", "sections": ["cleaning", "quality", "knowledge"]}
    state["steps"].append("report")
    return state


async def run_pipeline(state: State) -> State:
    """显式编排：clean → evaluate → (manual_review) → extract → insight → report。

    单步失败只标记 degraded 并继续（洞察失败不阻塞报告），最终返回完整 state。
    """
    state.setdefault("steps", [])
    state.setdefault("errors", [])
    for node in (_clean, _evaluate):
        state = await node(state)

    if state.get("needs_review"):
        state = await _manual_review(state)

    for node in (_extract, _insight, _report):
        try:
            state = await node(state)
        except Exception as exc:  # noqa: BLE001 - 原型演示编排容错
            state["status"] = "degraded"
            state["errors"].append({"node": node.__name__, "error": str(exc)})

    state.setdefault("status", "completed")
    return state


async def test_main_chain_runs_all_steps() -> None:
    state = await run_pipeline({"datasource_id": "ds-1", "seed_score": 88})
    assert state["status"] == "completed"
    assert state["steps"] == ["clean", "evaluate", "extract", "insight", "report"]
    assert state["report"]["status"] == "completed"
    print(f"\n[POC-3] 主链通过：steps={state['steps']}")


async def test_low_score_triggers_manual_review_and_continues() -> None:
    state = await run_pipeline({"datasource_id": "ds-2", "seed_score": 55})
    assert state["needs_review"] is True
    assert "manual_review" in state["steps"]
    assert state["steps"].index("manual_review") < state["steps"].index("extract")
    assert state["report"]["status"] == "completed"
    print(f"\n[POC-3] 复核分支通过：steps={state['steps']}")


async def test_failed_insight_does_not_block_report() -> None:
    state = await run_pipeline({"datasource_id": "ds-3", "seed_score": 90, "fail_insight": True})
    assert state["status"] == "degraded"
    assert state["errors"][0]["node"] == "_insight"
    assert state["report"]["status"] == "completed"
    assert "report" in state["steps"]
    print(f"\n[POC-3] 降级不阻塞：status={state['status']} errors={state['errors']}")
