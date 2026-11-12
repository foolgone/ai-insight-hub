"""问题分类 TOP（#6）与洞察批次对比（#3）的接口测试。"""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import (
    AnalysisResultFactory,
    CleanedDataFactory,
    DataSourceFactory,
    RawDataFactory,
    TaskFactory,
    persist,
)

pytestmark = pytest.mark.integration


async def _datasource(session: AsyncSession, user) -> tuple:
    datasource = DataSourceFactory(user_id=user.id)
    raw = RawDataFactory(datasource_id=datasource.id)
    await persist(session, datasource, raw)
    return datasource, raw


async def test_issue_categories_for_run(client, auth_headers, db_session, test_user) -> None:
    datasource, raw = await _datasource(db_session, test_user)
    cleaned = CleanedDataFactory(datasource_id=datasource.id, raw_data_id=raw.id)
    await persist(db_session, cleaned)
    task = TaskFactory(
        user_id=test_user.id,
        datasource_id=datasource.id,
        task_type="evaluate",
        status="completed",
        result={"evaluated": 2},
    )
    await persist(db_session, task)
    await persist(
        db_session,
        AnalysisResultFactory(
            datasource_id=datasource.id,
            data_id=cleaned.id,
            task_id=task.id,
            result={
                "overall_score": 60,
                "dimensions": {},
                "issue_items": [
                    {"category": "hallucination", "detail": "编造了优惠"},
                    {"category": "missing_knowledge", "detail": "没答运费"},
                    {"category": "missing_knowledge", "detail": "没答时效"},
                ],
            },
        ),
    )

    response = await client.get(
        f"/api/v1/datasources/{datasource.id}/analysis/quality/issues",
        headers=auth_headers,
        params={"run_id": str(task.id)},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["run_id"] == str(task.id)
    assert body["total_issues"] == 3
    assert body["items"][0]["category"] == "missing_knowledge"
    assert body["items"][0]["count"] == 2
    assert body["items"][0]["label"] == "知识缺失"
    assert "没答运费" in body["items"][0]["samples"]


async def test_issue_categories_default_to_latest_run(
    client, auth_headers, db_session, test_user
) -> None:
    datasource, _ = await _datasource(db_session, test_user)

    response = await client.get(
        f"/api/v1/datasources/{datasource.id}/analysis/quality/issues", headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json()["items"] == []


async def test_insight_compare_endpoint(client, auth_headers, db_session, test_user) -> None:
    datasource, _ = await _datasource(db_session, test_user)
    base = TaskFactory(
        user_id=test_user.id, datasource_id=datasource.id, task_type="analyze", status="completed"
    )
    target = TaskFactory(
        user_id=test_user.id, datasource_id=datasource.id, task_type="analyze", status="completed"
    )
    await persist(db_session, base, target)
    await persist(
        db_session,
        AnalysisResultFactory(
            datasource_id=datasource.id,
            data_id=None,
            task_id=base.id,
            analysis_type="insight",
            result={
                "sentiment_distribution": {"正面": 0.3, "负面": 0.2},
                "intent_distribution": {"退款": 10, "物流": 4},
                "pain_points": [{"pain_point": "退款慢"}],
            },
        ),
    )
    await persist(
        db_session,
        AnalysisResultFactory(
            datasource_id=datasource.id,
            data_id=None,
            task_id=target.id,
            analysis_type="insight",
            result={
                "sentiment_distribution": {"正面": 0.5, "负面": 0.1},
                "intent_distribution": {"退款": 6, "物流": 9},
                "pain_points": [{"pain_point": "发票慢"}],
            },
        ),
    )

    response = await client.get(
        f"/api/v1/datasources/{datasource.id}/runs/{base.id}/insight-compare/{target.id}",
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    sentiment = {item["name"]: item for item in body["sentiment"]}
    assert sentiment["负面"]["delta"] == -0.1
    intents = {item["name"]: item for item in body["intents"]}
    assert intents["物流"]["delta"] == 5
    assert body["pain_points_added"] == ["发票慢"]
    assert body["pain_points_removed"] == ["退款慢"]


async def test_insight_compare_rejects_same_run(
    client, auth_headers, db_session, test_user
) -> None:
    datasource, _ = await _datasource(db_session, test_user)
    task = TaskFactory(
        user_id=test_user.id, datasource_id=datasource.id, task_type="analyze", status="completed"
    )
    await persist(db_session, task)

    response = await client.get(
        f"/api/v1/datasources/{datasource.id}/runs/{task.id}/insight-compare/{task.id}",
        headers=auth_headers,
    )

    assert response.status_code == 422


async def test_insight_compare_rejects_non_insight_task(
    client, auth_headers, db_session, test_user
) -> None:
    datasource, _ = await _datasource(db_session, test_user)
    insight = TaskFactory(
        user_id=test_user.id, datasource_id=datasource.id, task_type="analyze", status="completed"
    )
    evaluate = TaskFactory(
        user_id=test_user.id, datasource_id=datasource.id, task_type="evaluate", status="completed"
    )
    await persist(db_session, insight, evaluate)

    response = await client.get(
        f"/api/v1/datasources/{datasource.id}/runs/{insight.id}/insight-compare/{evaluate.id}",
        headers=auth_headers,
    )

    assert response.status_code == 422
