"""B-502 种子知识库集成测试。"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select

from app.data.seed_knowledge import SEED_KNOWLEDGE, seed_knowledge
from app.models import KnowledgeBase
from tests.factories import DataSourceFactory, UserFactory, persist

pytestmark = pytest.mark.integration


async def test_seed_knowledge_is_idempotent(db_session) -> None:
    user = UserFactory()
    await persist(db_session, user)
    datasource = DataSourceFactory(user_id=user.id)
    await persist(db_session, datasource)
    expected = len(SEED_KNOWLEDGE)

    assert expected >= 30, "冷启动种子知识库目标 30+ 条"
    assert await seed_knowledge(db_session, datasource.id) == expected
    assert await seed_knowledge(db_session, datasource.id) == 0

    rows = (
        (
            await db_session.execute(
                select(KnowledgeBase).where(KnowledgeBase.datasource_id == datasource.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == expected
    assert all(row.is_seed for row in rows)
    assert all(row.source == "seed" for row in rows)
    assert all(row.status == "active" for row in rows)


async def test_create_datasource_with_seed_flag(client, auth_headers, db_session) -> None:
    response = await client.post(
        "/api/v1/datasources",
        headers=auth_headers,
        json={
            "name": "seed-init-ds",
            "type": "customer_service",
            "init_seed_knowledge": True,
        },
    )

    assert response.status_code == 201, response.text
    datasource_id = uuid.UUID(response.json()["id"])
    total = await db_session.scalar(
        select(func.count())
        .select_from(KnowledgeBase)
        .where(KnowledgeBase.datasource_id == datasource_id)
    )
    assert total == len(SEED_KNOWLEDGE)
