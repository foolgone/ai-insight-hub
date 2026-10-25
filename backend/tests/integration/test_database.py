"""B-203 数据库层集成测试（真实 PostgreSQL）。

需要 ``DATABASE_URL`` 指向可用的 PostgreSQL（本地 VM 5433 或 CI 服务）。
"""
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal, engine

pytestmark = pytest.mark.integration


async def test_engine_can_connect() -> None:
    async with engine.connect() as conn:
        value = (await conn.execute(text("SELECT 1"))).scalar_one()
    assert value == 1


async def test_session_can_query() -> None:
    async with SessionLocal() as session:
        assert isinstance(session, AsyncSession)
        value = (await session.execute(text("SELECT current_database()"))).scalar_one()
    assert value


async def test_pgvector_extension_available() -> None:
    """数据库扩展就绪（B-204/B-205 的向量列依赖它）。"""
    async with engine.connect() as conn:
        extensions = {
            row[0] for row in (await conn.execute(text("SELECT extname FROM pg_extension"))).all()
        }
    assert {"vector", "pg_trgm", "pgcrypto"} <= extensions
