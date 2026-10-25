"""B-403 / B-404 质量评估服务与 API 集成测试。"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.agents.base import AgentResult
from app.models import AnalysisResult
from app.services import evaluation_service
from tests.factories import (
    AnalysisResultFactory,
    CleanedDataFactory,
    DataSourceFactory,
    TaskFactory,
    UserFactory,
    persist,
)

pytestmark = pytest.mark.integration

_DIALOGUES = [
    {
        "dialogue_id": str(uuid.uuid4()),
        "timestamp": "2025-01-15T10:30:00",
        "user_message": "iPhone 14 多少钱",
        "ai_response": "5999 元起",
        "quality_score": 95.0,
        "issues": [],
    },
    {
        "dialogue_id": str(uuid.uuid4()),
        "timestamp": None,
        "user_message": "可以分期吗",
        "ai_response": "支持花呗 12 期",
        "quality_score": 85.0,
        "issues": [],
    },
]

_EVALUATION = {
    "dialogue_id": "d-1",
    "overall_score": 86.2,
    "dimensions": {
        "accuracy": {"score": 90, "issues": []},
        "completeness": {"score": 80, "issues": []},
        "hallucination": {"score": 82, "issues": []},
        "tone": {"score": 88, "issues": []},
        "compliance": {"score": 95, "issues": []},
    },
    "has_issues": False,
    "critical_issues": [],
    "minor_issues": [],
    "suggestions": [],
    "quality_level": "good",
    "needs_review": False,
}


class _FakeAgent:
    def __init__(self, result: AgentResult) -> None:
        self._result = result

    async def evaluate(self, input_data, **kwargs) -> AgentResult:
        return self._result


def _success_result() -> AgentResult:
    return AgentResult(
        success=True,
        data=dict(_EVALUATION),
        metadata={"agent": "evaluation_agent", "version": "v1.0.0", "model": "fake"},
        duration=1.0,
        token_usage={"input": 100, "output": 50},
    )


async def _setup(db_session, *, cleaned: int = 2) -> tuple:
    user = UserFactory()
    await persist(db_session, user)
    datasource = DataSourceFactory(user_id=user.id)
    await persist(db_session, datasource)
    for dialogue in _DIALOGUES[:cleaned]:
        await persist(
            db_session,
            CleanedDataFactory(
                datasource_id=datasource.id,
                dialogue_id=uuid.UUID(dialogue["dialogue_id"]),
                user_message=dialogue["user_message"],
                ai_response=dialogue["ai_response"],
                quality_score=dialogue["quality_score"],
                issues=[],
            ),
        )
    task = TaskFactory(
        user_id=user.id,
        datasource_id=datasource.id,
        task_type="evaluate",
        status="pending",
        params={"data_ids": [], "config": {}},
    )
    await persist(db_session, task)
    return user, datasource, task


async def test_run_evaluation_task_writes_analysis_results(db_session, monkeypatch) -> None:
    _, datasource, task = await _setup(db_session)
    monkeypatch.setattr(evaluation_service, "_build_agent", lambda: _FakeAgent(_success_result()))

    outcome = await evaluation_service.run_evaluation_task(str(task.id), session=db_session)

    assert outcome["status"] == "completed"
    assert outcome["evaluated"] == 2

    rows = (
        (
            await db_session.execute(
                select(AnalysisResult).where(AnalysisResult.datasource_id == datasource.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 2
    assert all(row.analysis_type == "quality" for row in rows)
    assert rows[0].result["overall_score"] == 86.2
    assert rows[0].agent_name == "evaluation_agent"

    await db_session.refresh(task)
    assert task.status == "completed"
    assert task.result["evaluated"] == 2
    assert task.progress == 100


async def test_run_evaluation_task_without_targets_fails(db_session, monkeypatch) -> None:
    _, _, task = await _setup(db_session, cleaned=0)
    monkeypatch.setattr(evaluation_service, "_build_agent", lambda: _FakeAgent(_success_result()))

    outcome = await evaluation_service.run_evaluation_task(str(task.id), session=db_session)

    assert outcome["status"] == "failed"
    await db_session.refresh(task)
    assert "no cleaned data" in (task.error_message or "")


async def test_run_evaluation_task_failure_path(db_session, monkeypatch) -> None:
    _, _, task = await _setup(db_session)
    monkeypatch.setattr(
        evaluation_service,
        "_build_agent",
        lambda: _FakeAgent(AgentResult(success=False, errors=["boom"])),
    )

    outcome = await evaluation_service.run_evaluation_task(str(task.id), session=db_session)

    assert outcome["status"] == "failed"


async def test_analyze_quality_endpoint_queues_task(client, auth_headers, monkeypatch) -> None:
    response = await client.post(
        "/api/v1/datasources",
        headers=auth_headers,
        json={"name": "evaluate-ds", "type": "customer_service"},
    )
    datasource_id = response.json()["id"]
    monkeypatch.setattr(evaluation_service, "enqueue_evaluation", lambda task: "celery-123")

    submitted = await client.post(
        f"/api/v1/datasources/{datasource_id}/analyze/quality",
        headers=auth_headers,
    )

    assert submitted.status_code == 202, submitted.text
    body = submitted.json()
    assert body["task_id"]
    assert body["estimated_duration"] >= 5.0


async def test_list_quality_analysis_with_summary(client, auth_headers, db_session) -> None:
    response = await client.post(
        "/api/v1/datasources",
        headers=auth_headers,
        json={"name": "evaluate-list-ds", "type": "customer_service"},
    )
    datasource_id = response.json()["id"]
    await persist(
        db_session,
        AnalysisResultFactory(
            datasource_id=uuid.UUID(datasource_id),
            analysis_type="quality",
            result={
                "overall_score": 86.2,
                "needs_review": False,
                "quality_level": "good",
                "dimensions": {
                    "accuracy": {"score": 90, "issues": []},
                    "completeness": {"score": 80, "issues": []},
                },
            },
        ),
    )

    listed = await client.get(
        f"/api/v1/datasources/{datasource_id}/analysis/quality",
        headers=auth_headers,
    )

    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert body["pagination"]["total"] == 1
    assert body["items"][0]["overall_score"] == 86.2
    assert body["summary"]["total"] == 1
    assert body["summary"]["avg_overall_score"] == 86.2
    assert body["summary"]["dimension_averages"]["accuracy"] == 90.0


async def test_review_endpoint_updates_result(client, auth_headers, db_session) -> None:
    response = await client.post(
        "/api/v1/datasources",
        headers=auth_headers,
        json={"name": "evaluate-review-ds", "type": "customer_service"},
    )
    datasource_id = response.json()["id"]
    row = AnalysisResultFactory(
        datasource_id=uuid.UUID(datasource_id),
        analysis_type="quality",
        result={
            "overall_score": 60.0,
            "needs_review": True,
            "quality_level": "fair",
            "dimensions": {
                "accuracy": {"score": 60, "issues": []},
                "completeness": {"score": 60, "issues": []},
            },
        },
    )
    await persist(db_session, row)

    reviewed = await client.post(
        f"/api/v1/datasources/{datasource_id}/analysis/quality/{row.id}/review",
        headers=auth_headers,
        json={
            "decision": "corrected",
            "note": "人工校准",
            "corrected_scores": {"accuracy": 90},
        },
    )

    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["needs_review"] is False
    await db_session.refresh(row)
    assert row.result["review"]["decision"] == "corrected"
    assert row.result["needs_review"] is False
    assert row.result["dimensions"]["accuracy"]["score"] == 90.0
    assert row.result["overall_score"] > 60.0


async def test_review_not_found(client, auth_headers) -> None:
    response = await client.post(
        "/api/v1/datasources",
        headers=auth_headers,
        json={"name": "evaluate-404-ds", "type": "customer_service"},
    )
    datasource_id = response.json()["id"]

    reviewed = await client.post(
        f"/api/v1/datasources/{datasource_id}/analysis/quality/{uuid.uuid4()}/review",
        headers=auth_headers,
        json={"decision": "approved"},
    )

    assert reviewed.status_code == 404
