"""批次列表与批次对比 API 集成测试（迁移 016 起的 ``analysis_results.task_id``）。"""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
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


def _evaluation(score: float, *, issues: list[str] | None = None, needs_review=False) -> dict:
    issues = issues or []
    return {
        "overall_score": score,
        "dimensions": {
            "accuracy": {"score": score - 2, "issues": issues},
            "completeness": {"score": score, "issues": []},
            "hallucination": {"score": score + 2, "issues": []},
            "tone": {"score": score, "issues": []},
            "compliance": {"score": score, "issues": []},
        },
        "needs_review": needs_review,
        "quality_level": "good",
    }


async def _datasource(session: AsyncSession, user) -> tuple:
    datasource = DataSourceFactory(user_id=user.id)
    raw = RawDataFactory(datasource_id=datasource.id)
    await persist(session, datasource, raw)
    dialogues = []
    for _ in range(2):
        item = CleanedDataFactory(datasource_id=datasource.id, raw_data_id=raw.id)
        dialogues.append(item)
    await persist(session, *dialogues)
    return datasource, dialogues


async def _completed_run(
    session: AsyncSession,
    *,
    user,
    datasource,
    scores: list[tuple[uuid.UUID, float]],
    issues: list[str] | None = None,
) -> object:
    task = TaskFactory(
        user_id=user.id,
        datasource_id=datasource.id,
        task_type="evaluate",
        status="completed",
        result={"evaluated": len(scores), "failed": 0, "needs_review": 0, "total": len(scores)},
        params={"data_ids": [], "config": {}},
    )
    await persist(session, task)
    rows = [
        AnalysisResultFactory(
            datasource_id=datasource.id,
            data_id=data_id,
            task_id=task.id,
            result=_evaluation(score, issues=issues),
        )
        for data_id, score in scores
    ]
    await persist(session, *rows)
    return task


async def test_list_runs_returns_aggregates(
    client: AsyncClient, db_session: AsyncSession, auth_headers: dict, test_user
) -> None:
    datasource, dialogues = await _datasource(db_session, test_user)
    run_a = await _completed_run(
        db_session,
        user=test_user,
        datasource=datasource,
        scores=[(dialogues[0].id, 60.0), (dialogues[1].id, 70.0)],
    )
    run_b = await _completed_run(
        db_session, user=test_user, datasource=datasource, scores=[(dialogues[0].id, 90.0)]
    )

    response = await client.get(f"/api/v1/datasources/{datasource.id}/runs", headers=auth_headers)

    assert response.status_code == 200, response.text
    items = {item["task_id"]: item for item in response.json()["items"]}
    assert set(items) == {str(run_a.id), str(run_b.id)}
    assert items[str(run_a.id)]["sample_count"] == 2
    assert items[str(run_a.id)]["avg_overall_score"] == 65.0
    assert items[str(run_a.id)]["evaluated"] == 2
    assert items[str(run_b.id)]["avg_overall_score"] == 90.0


async def test_compare_runs_reports_deltas(
    client: AsyncClient, db_session: AsyncSession, auth_headers: dict, test_user
) -> None:
    datasource, dialogues = await _datasource(db_session, test_user)
    base = await _completed_run(
        db_session,
        user=test_user,
        datasource=datasource,
        scores=[(dialogues[0].id, 60.0), (dialogues[1].id, 70.0)],
        issues=["未回答运费问题"],
    )
    target = await _completed_run(
        db_session,
        user=test_user,
        datasource=datasource,
        scores=[(dialogues[0].id, 75.0), (dialogues[1].id, 65.0)],
        issues=["回答超出知识库范围"],
    )

    response = await client.get(
        f"/api/v1/datasources/{datasource.id}/runs/{base.id}/compare/{target.id}",
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["base"]["avg_overall_score"] == 65.0
    assert payload["target"]["avg_overall_score"] == 70.0
    assert payload["delta"]["avg_overall_score"] == 5.0
    assert payload["improvements"][0]["delta"] == 15.0
    assert payload["regressions"][0]["delta"] == -5.0
    assert payload["added_items"] == 0
    assert any("超出知识库" in item for item in payload["issues_added"])
    assert any("运费" in item for item in payload["issues_removed"])


async def test_compare_rejects_same_run(
    client: AsyncClient, db_session: AsyncSession, auth_headers: dict, test_user
) -> None:
    datasource, dialogues = await _datasource(db_session, test_user)
    run = await _completed_run(
        db_session, user=test_user, datasource=datasource, scores=[(dialogues[0].id, 80.0)]
    )

    response = await client.get(
        f"/api/v1/datasources/{datasource.id}/runs/{run.id}/compare/{run.id}",
        headers=auth_headers,
    )

    assert response.status_code == 422


async def test_compare_rejects_unfinished_run(
    client: AsyncClient, db_session: AsyncSession, auth_headers: dict, test_user
) -> None:
    datasource, dialogues = await _datasource(db_session, test_user)
    done = await _completed_run(
        db_session, user=test_user, datasource=datasource, scores=[(dialogues[0].id, 80.0)]
    )
    pending = TaskFactory(
        user_id=test_user.id,
        datasource_id=datasource.id,
        task_type="evaluate",
        status="running",
    )
    await persist(db_session, pending)

    response = await client.get(
        f"/api/v1/datasources/{datasource.id}/runs/{done.id}/compare/{pending.id}",
        headers=auth_headers,
    )

    assert response.status_code == 409


async def test_compare_rejects_legacy_run_without_task_link(
    client: AsyncClient, db_session: AsyncSession, auth_headers: dict, test_user
) -> None:
    """迁移 016 之前的批次没有 task_id，不能假装能对比。"""
    datasource, _ = await _datasource(db_session, test_user)
    legacy = TaskFactory(
        user_id=test_user.id,
        datasource_id=datasource.id,
        task_type="evaluate",
        status="completed",
        result={"evaluated": 1},
    )
    await persist(db_session, legacy)
    # 结果存在，但没有挂 task_id
    await persist(db_session, AnalysisResultFactory(datasource_id=datasource.id))

    newer = await _completed_run(
        db_session, user=test_user, datasource=datasource, scores=[(uuid.uuid4(), 80.0)]
    )

    response = await client.get(
        f"/api/v1/datasources/{datasource.id}/runs/{legacy.id}/compare/{newer.id}",
        headers=auth_headers,
    )

    assert response.status_code == 409
    assert "legacy" in response.json()["error"]["message"].lower()


async def test_compare_rejects_run_from_other_datasource(
    client: AsyncClient, db_session: AsyncSession, auth_headers: dict, test_user
) -> None:
    datasource, dialogues = await _datasource(db_session, test_user)
    other, other_dialogues = await _datasource(db_session, test_user)
    base = await _completed_run(
        db_session, user=test_user, datasource=datasource, scores=[(dialogues[0].id, 80.0)]
    )
    foreign = await _completed_run(
        db_session, user=test_user, datasource=other, scores=[(other_dialogues[0].id, 90.0)]
    )

    response = await client.get(
        f"/api/v1/datasources/{datasource.id}/runs/{base.id}/compare/{foreign.id}",
        headers=auth_headers,
    )

    assert response.status_code == 404
