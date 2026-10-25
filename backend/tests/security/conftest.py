"""安全测试专用设施（复用集成测试的事务 DB + 异步客户端模式）。

注意：这里显式定义 fixtures（而不是通过 pytest_plugins 引入），
避免根 ``tests/conftest.py`` 的同步 ``client`` 覆盖异步客户端。
"""
from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import engine, get_db
from app.core.redis import close_redis
from app.core.security import hash_password
from app.main import app
from tests.factories import UserFactory, persist

TEST_USER_PASSWORD = "secret123"


@pytest.fixture(autouse=True)
async def dispose_resources_between_tests() -> AsyncIterator[None]:
    await engine.dispose()
    await close_redis()
    yield
    await engine.dispose()
    await close_redis()


@pytest.fixture(autouse=True)
def disable_rate_limit(monkeypatch) -> None:
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", False)


@pytest.fixture()
async def db_session() -> AsyncIterator[AsyncSession]:
    async with engine.connect() as conn:
        transaction = await conn.begin()
        session = AsyncSession(
            bind=conn,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield session
        finally:
            await session.close()
            if transaction.is_active:
                await transaction.rollback()


@pytest.fixture()
async def client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    async def _get_db_override() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _get_db_override
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
async def test_user(db_session: AsyncSession):
    user = UserFactory(password_hash=hash_password(TEST_USER_PASSWORD))
    await persist(db_session, user)
    return user


@pytest.fixture()
async def auth_headers(client: AsyncClient, test_user) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": test_user.email, "password": TEST_USER_PASSWORD},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
