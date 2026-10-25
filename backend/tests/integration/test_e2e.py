"""B-606 端到端集成测试：上传 → 清洗 → 评估 → 提取 → 报告（DB 一致性）。"""
from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import func, select

from app.agents.base import AgentResult
from app.models import (
    AnalysisResult,
    CleanedData,
    DataSource,
    KnowledgeBase,
    RawData,
    Report,
)
from app.services import (
    cleaning_service,
    evaluation_service,
    knowledge_service,
    report_service,
    storage_service,
)

pytestmark = pytest.mark.integration

_CLEANED = [
    {
        "dialogue_id": "line-1",
        "timestamp": "2025-01-15T10:30:00",
        "user_message": "iPhone 14 多少钱",
        "ai_response": "5999 元起",
        "quality_score": 95.0,
        "issues": [],
    },
    {
        "dialogue_id": "line-2",
        "timestamp": "2025-01-16T11:00:00",
        "user_message": "怎么退货",
        "ai_response": "订单页申请退货",
        "quality_score": 85.0,
        "issues": [],
    },
]

_EVALUATION = {
    "dialogue_id": "d-1",
    "overall_score": 88.0,
    "dimensions": {
        "accuracy": {"score": 90, "issues": []},
        "completeness": {"score": 85, "issues": []},
        "hallucination": {"score": 88, "issues": []},
        "tone": {"score": 90, "issues": []},
        "compliance": {"score": 95, "issues": []},
    },
    "has_issues": False,
    "critical_issues": [],
    "minor_issues": [],
    "suggestions": [],
    "quality_level": "good",
    "needs_review": False,
}

_EXTRACTION = {
    "datasource_id": str(uuid.uuid4()),
    "faqs": [
        {
            "question": "iPhone 14 多少钱？",
            "answer": "5999 元起。",
            "category": "价格",
            "variations": [],
            "confidence": 0.95,
            "source_dialogue_ids": [],
            "embedding": None,
        },
        {
            "question": "如何退货？",
            "answer": "在订单页申请退货。",
            "category": "售后",
            "variations": [],
            "confidence": 0.9,
            "source_dialogue_ids": [],
            "embedding": None,
        },
    ],
    "gaps": [{"question": "能否开发票？", "frequency": 2, "category": "发票"}],
    "stats": {"kept": 2},
}

_REPORT = {
    "title": "综合分析报告",
    "report_type": "comprehensive",
    "generated_at": "2025-01-20T10:00:00",
    "summary": "整体表现良好。",
    "sections": [{"title": "概览", "content": "共 2 条对话。"}],
    "highlights": ["平均分 88"],
    "recommendations": ["补充发票知识"],
    "metadata": {"insight_degraded": True},
}


class _FakeAgentBase:
    """假 Agent 基类（便于统一构造）。"""


def _agent_result(data: dict[str, Any]) -> AgentResult:
    return AgentResult(
        success=True,
        data=data,
        metadata={"agent": "fake", "version": "v1.0.0"},
        duration=0.1,
        token_usage={"input": 10, "output": 5},
    )


class CleanAgent:
    async def clean(self, input_data, **kwargs) -> AgentResult:
        return _agent_result({"dialogues": _CLEANED})


class EvalAgent:
    async def evaluate(self, input_data, **kwargs) -> AgentResult:
        return _agent_result(dict(_EVALUATION))


class ExtractAgent:
    async def extract(self, input_data, **kwargs) -> AgentResult:
        return _agent_result(dict(_EXTRACTION))


class ReportAgent:
    async def generate(self, input_data, **kwargs) -> AgentResult:
        return _agent_result(dict(_REPORT))


async def test_full_pipeline_e2e(client, auth_headers, db_session, monkeypatch) -> None:
    monkeypatch.setattr(cleaning_service, "_build_agent", lambda: CleanAgent())
    monkeypatch.setattr(cleaning_service, "enqueue_clean", lambda task: "celery-clean")
    monkeypatch.setattr(evaluation_service, "_build_agent", lambda: EvalAgent())
    monkeypatch.setattr(evaluation_service, "enqueue_evaluation", lambda task: "celery-eval")
    monkeypatch.setattr(knowledge_service, "_build_agent", lambda: ExtractAgent())
    monkeypatch.setattr(knowledge_service, "enqueue_extract", lambda task: "celery-extract")
    monkeypatch.setattr(report_service, "_build_agent", lambda: ReportAgent())
    monkeypatch.setattr(report_service, "enqueue_report", lambda report: "celery-report")

    # 1) 数据源 + 上传
    created = await client.post(
        "/api/v1/datasources",
        headers=auth_headers,
        json={"name": "e2e-ds", "type": "customer_service"},
    )
    assert created.status_code == 201, created.text
    datasource_id = created.json()["id"]

    uploaded = await client.post(
        f"/api/v1/datasources/{datasource_id}/upload",
        headers=auth_headers,
        files={
            "file": (
                "dialogues.csv",
                "user_message,ai_response\n怎么退货,订单页申请\n",
                "text/csv",
            )
        },
    )
    assert uploaded.status_code == 202, uploaded.text

    raw = await db_session.scalar(
        select(RawData).where(RawData.datasource_id == uuid.UUID(datasource_id))
    )
    assert raw is not None and raw.status == "pending"

    # 2) 清洗（upload 已自动创建并排队 clean 任务，直接复用该任务）
    assert uploaded.json()["task_id"]
    clean_task_id = uploaded.json()["task_id"]
    outcome = await cleaning_service.run_clean_task(clean_task_id, session=db_session)
    assert outcome["status"] == "completed"
    cleaned_count = await db_session.scalar(
        select(func.count())
        .select_from(CleanedData)
        .where(CleanedData.datasource_id == uuid.UUID(datasource_id))
    )
    assert cleaned_count == 2

    # 3) 质量评估
    evaluated = await client.post(
        f"/api/v1/datasources/{datasource_id}/analyze/quality",
        headers=auth_headers,
        json={},
    )
    assert evaluated.status_code == 202, evaluated.text
    eval_outcome = await evaluation_service.run_evaluation_task(
        evaluated.json()["task_id"], session=db_session
    )
    assert eval_outcome["status"] == "completed"
    quality_count = await db_session.scalar(
        select(func.count())
        .select_from(AnalysisResult)
        .where(
            AnalysisResult.datasource_id == uuid.UUID(datasource_id),
            AnalysisResult.analysis_type == "quality",
        )
    )
    assert quality_count == 2

    # 4) 知识提取
    extracted = await client.post(
        f"/api/v1/datasources/{datasource_id}/extract-knowledge",
        headers=auth_headers,
        json={},
    )
    assert extracted.status_code == 202, extracted.text
    extract_outcome = await knowledge_service.run_extraction_task(
        extracted.json()["task_id"], session=db_session
    )
    assert extract_outcome["status"] == "completed"
    faq_count = await db_session.scalar(
        select(func.count())
        .select_from(KnowledgeBase)
        .where(KnowledgeBase.datasource_id == uuid.UUID(datasource_id))
    )
    assert faq_count == 2

    # 5) 报告
    report_response = await client.post(
        f"/api/v1/datasources/{datasource_id}/reports",
        headers=auth_headers,
        json={
            "title": "端到端报告",
            "report_type": "comprehensive",
            "format": "markdown",
        },
    )
    assert report_response.status_code == 202, report_response.text
    report_id = report_response.json()["id"]
    report_outcome = await report_service.run_report_task(report_id, session=db_session)
    assert report_outcome["status"] == "completed"

    report_row = await db_session.get(Report, uuid.UUID(report_id))
    assert report_row is not None
    assert report_row.status == "completed"
    assert report_row.file_size and report_row.file_size > 0
    assert report_row.file_path

    content = storage_service.read_bytes(report_row.file_path)
    assert "端到端报告".encode("utf-8") in content

    # 6) 数据一致性
    datasource = await db_session.get(DataSource, uuid.UUID(datasource_id))
    assert datasource is not None
    assert datasource.workflow_status in {"data_cleaned", "knowledge_built", "ready"}
    assert datasource.statistics["cleaned_records"] == 2
