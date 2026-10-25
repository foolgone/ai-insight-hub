"""B-206 测试基础设施验证（事务隔离 / 异步 client / 数据工厂）。"""
from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.core.database import get_db
from app.main import app
from app.models import DataSource, User
from tests.factories import DataSourceFactory, UserFactory, persist

pytestmark = pytest.mark.integration


async def test_db_session_rollback_discards_data(db_session) -> None:
    user = UserFactory()
    await persist(db_session, user)
    assert await db_session.get(User, user.id) is not None

    await db_session.rollback()

    assert await db_session.get(User, user.id) is None


async def test_factories_persist_rows_with_db_defaults(db_session) -> None:
    user = UserFactory()
    await persist(db_session, user)
    source = DataSourceFactory(user_id=user.id)
    await persist(db_session, source)
    await db_session.refresh(source)

    assert source.id is not None
    assert source.status == "active"
    assert source.workflow_status == "created"
    assert source.config is not None
    assert source.config["auto_clean"] is True

    count = await db_session.scalar(
        select(func.count()).select_from(DataSource).where(DataSource.user_id == user.id)
    )
    assert count == 1


async def test_async_client_serves_health(client) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


async def test_async_client_uses_unified_error_body(client) -> None:
    response = await client.get("/api/v1/not-exists")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "HTTP_ERROR"


async def test_client_dependency_override_is_active(client, db_session) -> None:
    assert get_db in app.dependency_overrides
    user = UserFactory()
    await persist(db_session, user)
    assert await db_session.get(User, user.id) is not None


async def test_test_user_and_auth_headers_work(client, test_user, auth_headers) -> None:
    response = await client.get("/api/v1/users/me", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["email"] == test_user.email
