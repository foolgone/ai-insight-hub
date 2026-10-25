"""集成测试公共设施。

- ``db_session``：每个用例独立事务 + savepoint，用例结束整体回滚，互不影响；
- ``client``：基于 ASGITransport 的异步客户端，``get_db`` 依赖被替换为 ``db_session``；
- 全局 ``engine`` 连接池会在用例前后释放，避免 pytest-asyncio 多事件循环导致的
  ``RuntimeError: Event loop is closed``。
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
    """集成测试默认关闭限流；限流用例自行开启（避免用例间计数干扰）。"""
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", False)


@pytest.fixture()
async def db_session() -> AsyncIterator[AsyncSession]:
    """事务隔离会话：用例内可见，结束后回滚。"""
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
    """异步 HTTP 客户端，数据库依赖指向测试事务会话。"""

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
    """已持久化的普通用户（密码见 ``TEST_USER_PASSWORD``）。"""
    user = UserFactory(password_hash=hash_password(TEST_USER_PASSWORD))
    await persist(db_session, user)
    return user


@pytest.fixture()
async def auth_headers(client: AsyncClient, test_user) -> dict[str, str]:
    """登录 ``test_user`` 后的 Authorization 头。"""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": test_user.email, "password": TEST_USER_PASSWORD},
    )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
