"""B-203 数据库层单测（不连库）。"""
from __future__ import annotations

import inspect

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.config import settings
from app.core.database import (
    SessionLocal,
    create_engine,
    dispose_engine,
    get_db,
    to_async_dsn,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("postgresql://u:p@host:5432/db", "postgresql+asyncpg://u:p@host:5432/db"),
        ("postgresql+psycopg2://u:p@host/db", "postgresql+asyncpg://u:p@host/db"),
        ("postgresql+asyncpg://u:p@host/db", "postgresql+asyncpg://u:p@host/db"),
        ("sqlite:///tmp.db", "sqlite:///tmp.db"),
    ],
)
def test_to_async_dsn(raw: str, expected: str) -> None:
    assert to_async_dsn(raw) == expected


def test_create_engine_uses_asyncpg_driver() -> None:
    engine = create_engine("postgresql://u:p@localhost:5432/db")
    assert isinstance(engine, AsyncEngine)
    assert engine.url.drivername == "postgresql+asyncpg"
    assert engine.url.database == "db"


def test_session_factory_configuration() -> None:
    assert SessionLocal.class_ is AsyncSession
    assert SessionLocal.kw["expire_on_commit"] is False
    assert SessionLocal.kw["autoflush"] is False


def test_get_db_is_async_generator_function() -> None:
    assert inspect.isasyncgenfunction(get_db)


async def test_get_db_yields_async_session() -> None:
    agen = get_db()
    session = await anext(agen)
    assert isinstance(session, AsyncSession)
    await agen.aclose()


async def test_dispose_engine_is_idempotent() -> None:
    await dispose_engine()
    await dispose_engine()


def test_create_engine_defaults_to_settings_url() -> None:
    engine = create_engine()
    assert engine.url.drivername == "postgresql+asyncpg"
    assert settings.DATABASE_POOL_SIZE >= 1
