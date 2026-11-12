"""周报汇总（#5）：任务/成本/盲区统计口径。"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KnowledgeGap, LlmCall
from app.tasks.digest import collect_digest
from tests.factories import DataSourceFactory, TaskFactory, UserFactory, persist

pytestmark = pytest.mark.integration


async def test_collect_digest_counts_recent_tasks_cost_and_gaps(
    db_session: AsyncSession,
) -> None:
    user = UserFactory()
    await persist(db_session, user)
    datasource = DataSourceFactory(user_id=user.id)
    await persist(db_session, datasource)

    completed = TaskFactory(
        user_id=user.id, datasource_id=datasource.id, task_type="clean", status="completed"
    )
    completed2 = TaskFactory(
        user_id=user.id, datasource_id=datasource.id, task_type="evaluate", status="completed"
    )
    failed = TaskFactory(
        user_id=user.id, datasource_id=datasource.id, task_type="extract", status="failed"
    )
    await persist(db_session, completed, completed2, failed)

    for key_source, cost in (("server", Decimal("0.05")), ("user", Decimal("0.10"))):
        await persist(
            db_session,
            LlmCall(
                id=uuid.uuid4(),
                user_id=user.id,
                datasource_id=datasource.id,
                task_id=completed.id,
                attempt=0,
                idempotency_key=f"digest-{key_source}",
                service="deepseek",
                model="deepseek-flash",
                input_tokens=100,
                output_tokens=50,
                total_tokens=150,
                input_cost=Decimal("0"),
                output_cost=Decimal("0"),
                total_cost=cost,
                key_source=key_source,
            ),
        )

    await persist(
        db_session,
        KnowledgeGap(
            id=uuid.uuid4(),
            datasource_id=datasource.id,
            question="支持发票吗？",
            question_key=f"key-{uuid.uuid4().hex[:8]}",
            status="open",
            hit_count=3,
        ),
    )

    payload = await collect_digest(db_session)

    assert payload["tasks_completed"] == 2
    assert payload["tasks_failed"] == 1
    assert payload["by_type"] == {"clean": 1, "evaluate": 1}
    # BYOK（key_source=user）不计入成本
    assert payload["cost"] == pytest.approx(0.05)
    assert payload["calls"] == 1
    assert payload["open_gaps"] >= 1
