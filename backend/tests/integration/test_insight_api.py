"""B-603 洞察服务与 API 集成测试。"""
from __future__ import annotations

import uuid

import pytest

from app.agents.base import AgentResult
from app.services import insight_service
from tests.factories import (
    CleanedDataFactory,
    DataSourceFactory,
    RawDataFactory,
    TaskFactory,
    UserFactory,
    persist,
)

pytestmark = pytest.mark.integration

_INSIGHT_DATA = {
    "datasource_id": str(uuid.uuid4()),
    "intent_distribution": {"咨询": 2},
    "top_questions": [{"question": "退货政策", "count": 2, "ratio": 1.0}],
    "sentiment_distribution": {"正面": 0.5, "中性": 0.5, "负面": 0.0},
    "sentiment_trend": [],
    "pain_points": [
        {
            "issue": "退货流程复杂",
            "frequency": 2,
            "severity": "medium",
            "suggestions": "简化流程",
        }
    ],
    "unresolved_issues": [],
    "emerging_topics": ["退货咨询增加"],
    "seasonal_patterns": None,
    "degraded": False,
    "statistics": {"dialogue_count": 2},
}


class _FakeAgent:
    def __init__(self, result: AgentResult) -> None:
        self._result = result

    async def analyze(self, input_data, **kwargs) -> AgentResult:
        return self._result


def _success_result() -> AgentResult:
    return AgentResult(
        success=True,
        data=dict(_INSIGHT_DATA),
        metadata={"agent": "insight_agent", "version": "v1.0.0"},
        duration=1.0,
        token_usage={"input": 200, "output": 100},
    )


async def _setup(db_session) -> tuple:
    user = UserFactory()
    await persist(db_session, user)
    datasource = DataSourceFactory(user_id=user.id)
    await persist(db_session, datasource)
    raw = RawDataFactory(datasource_id=datasource.id)
    await persist(db_session, raw)
    for index in range(2):
        await persist(
            db_session,
            CleanedDataFactory(
                datasource_id=datasource.id,
                raw_data_id=raw.id,
                user_message=f"怎么退货 {index}",
                ai_response="在订单页申请",
            ),
        )
    task = TaskFactory(
        user_id=user.id,
        datasource_id=datasource.id,
        task_type="analyze",
        status="pending",
        params={},
    )
    await persist(db_session, task)
    return user, datasource, task


async def test_run_insight_task_completes(db_session, monkeypatch) -> None:
    _, _, task = await _setup(db_session)
    monkeypatch.setattr(insight_service, "_build_agent", lambda: _FakeAgent(_success_result()))

    outcome = await insight_service.run_insight_task(str(task.id), session=db_session)

    assert outcome["status"] == "completed"
    await db_session.refresh(task)
    assert task.result["intent_distribution"] == {"咨询": 2}
    assert task.progress == 100


async def test_run_insight_task_without_data_fails(db_session, monkeypatch) -> None:
    user = UserFactory()
    await persist(db_session, user)
    datasource = DataSourceFactory(user_id=user.id)
    await persist(db_session, datasource)
    task = TaskFactory(
        user_id=user.id,
        datasource_id=datasource.id,
        task_type="analyze",
        status="pending",
        params={},
    )
    await persist(db_session, task)
    monkeypatch.setattr(insight_service, "_build_agent", lambda: _FakeAgent(_success_result()))

    outcome = await insight_service.run_insight_task(str(task.id), session=db_session)

    assert outcome["status"] == "failed"


async def test_analyze_insights_endpoint(client, auth_headers, monkeypatch) -> None:
    response = await client.post(
        "/api/v1/datasources",
        headers=auth_headers,
        json={"name": "insight-ds", "type": "customer_service"},
    )
    datasource_id = response.json()["id"]
    monkeypatch.setattr(insight_service, "enqueue_insight", lambda task: "celery-insight")

    submitted = await client.post(
        f"/api/v1/datasources/{datasource_id}/analyze/insights",
        headers=auth_headers,
    )

    assert submitted.status_code == 202, submitted.text
    assert submitted.json()["task_id"]


async def test_get_insights_returns_structure(
    client, auth_headers, db_session, monkeypatch, test_user
) -> None:
    datasource_id = uuid.uuid4()
    datasource = DataSourceFactory(id=datasource_id, user_id=test_user.id)
    await persist(db_session, datasource)
    task = TaskFactory(
        user_id=test_user.id,
        datasource_id=datasource_id,
        task_type="analyze",
        status="completed",
        params={"time_range": {"start": "2025-01-01", "end": "2025-01-31"}},
        result=dict(_INSIGHT_DATA),
    )
    await persist(db_session, task)

    response = await client.get(
        f"/api/v1/datasources/{datasource_id}/analysis/insights",
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "completed"
    assert body["intent_distribution"] == {"咨询": 2}
    assert body["top_questions"][0]["frequency"] == 2
    assert round(sum(body["sentiment_distribution"].values()), 4) == 1.0
    assert body["pain_points"][0]["issue"] == "退货流程复杂"


async def test_get_insights_empty(client, auth_headers, db_session) -> None:
    response = await client.post(
        "/api/v1/datasources",
        headers=auth_headers,
        json={"name": "insight-empty-ds", "type": "customer_service"},
    )
    datasource_id = response.json()["id"]

    fetched = await client.get(
        f"/api/v1/datasources/{datasource_id}/analysis/insights",
        headers=auth_headers,
    )

    assert fetched.status_code == 200
    assert fetched.json()["status"] == "empty"


async def test_insight_forbidden_for_other_user(
    client, auth_headers, db_session, test_user
) -> None:
    from app.core.security import hash_password

    datasource = DataSourceFactory(user_id=test_user.id)
    await persist(db_session, datasource)
    other = UserFactory(password_hash=hash_password("other12345"))
    await persist(db_session, other)
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": other.email, "password": "other12345"},
    )
    token = login.json()["access_token"]

    response = await client.get(
        f"/api/v1/datasources/{datasource.id}/analysis/insights",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


async def test_insight_task_registered() -> None:
    import app.tasks  # noqa: F401
    from app.core.celery import celery_app

    assert "tasks.analyze_insights" in celery_app.tasks
