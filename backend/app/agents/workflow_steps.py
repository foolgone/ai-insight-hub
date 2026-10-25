"""工作流默认节点适配器（B-604）：把真实 Agent 适配为 ``WorkflowState`` 步骤。"""
from __future__ import annotations

from typing import Any

from app.agents.workflow import StepFunc, WorkflowState


def build_default_steps(
    *,
    session: Any = None,
    task_id: Any = None,
    user_id: Any = None,
    cleaning_agent: Any = None,
    evaluation_agent: Any = None,
    extraction_agent: Any = None,
    insight_agent: Any = None,
    report_agent: Any = None,
) -> dict[str, StepFunc]:
    """构造 5 个 Agent 步骤（manual_review 由编排器内联处理）。"""
    from app.agents.cleaning_agent import DataCleaningAgent
    from app.agents.evaluation_agent import QualityEvaluationAgent
    from app.agents.extraction_agent import KnowledgeExtractionAgent
    from app.agents.insight_agent import InsightAnalysisAgent
    from app.agents.report_agent import ReportGenerationAgent

    agents = {
        "clean": cleaning_agent or DataCleaningAgent(),
        "evaluate": evaluation_agent or QualityEvaluationAgent(),
        "extract": extraction_agent or KnowledgeExtractionAgent(),
        "insight": insight_agent or InsightAnalysisAgent(),
        "report": report_agent or ReportGenerationAgent(),
    }
    common = {"session": session, "task_id": task_id, "user_id": user_id}

    async def invoke(name: str, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        result = await getattr(agents[name], method)(payload, **common)
        if not result.success or not result.data:
            raise RuntimeError(f"{name} failed: {'; '.join(result.errors)}")
        return result.data

    async def clean(state: WorkflowState) -> dict[str, Any]:
        data = await invoke(
            "clean",
            "clean",
            {
                "datasource_id": state.datasource_id,
                "raw_data": state.raw_data,
                "data_type": "txt",
            },
        )
        return {"cleaned_data": data.get("dialogues", [])}

    async def evaluate(state: WorkflowState) -> dict[str, Any]:
        results = []
        for dialogue in state.cleaned_data:
            result = await agents["evaluate"].evaluate({"dialogue": dialogue}, **common)
            if result.success and result.data:
                results.append(result.data)
        if not results:
            raise RuntimeError("evaluate failed: no dialogue evaluated")
        return {"evaluation_results": results}

    async def extract(state: WorkflowState) -> dict[str, Any]:
        data = await invoke(
            "extract",
            "extract",
            {
                "datasource_id": state.datasource_id,
                "dialogues": state.cleaned_data,
                "existing_questions": [],
            },
        )
        return {
            "knowledge_base": data.get("faqs", []),
            "knowledge_gaps": data.get("gaps", []),
        }

    async def insight(state: WorkflowState) -> dict[str, Any]:
        result = await agents["insight"].analyze(
            {
                "datasource_id": state.datasource_id,
                "dialogues": state.cleaned_data,
            },
            **common,
        )
        return {"insights": result.data if result.success else None}

    async def report(state: WorkflowState) -> dict[str, Any]:
        scores = [float(item.get("overall_score", 0)) for item in state.evaluation_results]
        data = await invoke(
            "report",
            "generate",
            {
                "datasource_id": state.datasource_id,
                "title": "综合分析报告",
                "report_type": "comprehensive",
                "data": {
                    "cleaning_statistics": {"total": len(state.cleaned_data)},
                    "quality_summary": {
                        "avg_score": round(sum(scores) / len(scores), 2) if scores else 0.0,
                        "needs_review_count": sum(
                            1 for item in state.evaluation_results if item.get("needs_review")
                        ),
                    },
                    "knowledge_summary": {"faq_count": len(state.knowledge_base)},
                    "insight_summary": state.insights,
                },
            },
        )
        return {"report": data}

    return {
        "clean": clean,
        "evaluate": evaluate,
        "extract": extract,
        "insight": insight,
        "report": report,
    }


__all__ = ["build_default_steps"]
