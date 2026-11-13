"""Agent 便捷入口的签名契约。

线上事故（2026-11-12）：``cleaning_service`` 给 ``agent.clean()`` 传了
``credentials=``，而凭据是**构造函数**注入的；入口曾用 ``**kwargs`` 转发，
于是错误在运行时才炸（``BaseAgent.invoke() got an unexpected keyword
argument 'credentials'``），清洗任务 100% 失败而 CI 全绿。

这里把契约固化：入口的关键字参数必须与 ``invoke`` 完全一致，
既不允许吞掉未知参数（``**kwargs``），也不允许漏参数。
"""
from __future__ import annotations

import inspect

import pytest

from app.agents.cleaning_agent import DataCleaningAgent
from app.agents.evaluation_agent import QualityEvaluationAgent
from app.agents.extraction_agent import KnowledgeExtractionAgent
from app.agents.insight_agent import InsightAnalysisAgent
from app.agents.report_agent import ReportGenerationAgent
from app.agents.structure_agent import TranscriptStructureAgent

pytestmark = pytest.mark.unit

ENTRIES = [
    (DataCleaningAgent, "clean"),
    (QualityEvaluationAgent, "evaluate"),
    (KnowledgeExtractionAgent, "extract"),
    (InsightAnalysisAgent, "analyze"),
    (ReportGenerationAgent, "generate"),
    (TranscriptStructureAgent, "structure"),
]


@pytest.mark.parametrize(("agent_cls", "method_name"), ENTRIES)
def test_convenience_entry_mirrors_invoke(agent_cls, method_name: str) -> None:
    entry = inspect.signature(getattr(agent_cls, method_name))
    invoke = inspect.signature(agent_cls.invoke)

    entry_params = set(entry.parameters) - {"self", "input_data"}
    invoke_params = set(invoke.parameters) - {"self", "input_data"}

    assert "kwargs" not in entry_params, (
        f"{agent_cls.__name__}.{method_name} 用 **kwargs 转发会吞掉拼错的参数，"
        "请显式列出 invoke 的关键字参数"
    )
    assert entry_params == invoke_params, (
        f"{agent_cls.__name__}.{method_name} 与 invoke 参数不一致："
        f"{sorted(entry_params)} != {sorted(invoke_params)}"
    )
    # 凭据只能走构造函数注入
    assert "credentials" not in entry_params


def test_clean_rejects_credentials_kwarg() -> None:
    """回归：曾把 credentials 传给 clean()，导致每次清洗任务立即失败。"""
    with pytest.raises(TypeError):
        DataCleaningAgent.clean(object(), credentials=None)  # type: ignore[call-arg]
