"""数据库引擎与会话（SQLAlchemy 2.0 async + asyncpg）。

约束（见数据库设计 §1.3/§8.2）：
- 连接串唯一来源：``settings.DATABASE_URL``，本模块负责补 ``+asyncpg`` 方言，禁止其它模块硬编码；
- 连接池参数全部来自配置：pool_size=20 / max_overflow=40 / pool_timeout=30 / pool_recycle=3600；
- API 层通过 ``get_db`` 依赖获取 ``AsyncSession``；集成测试可用
  ``app.dependency_overrides[get_db]`` 替换为测试会话。

Alembic 使用同步驱动（``migrations/env.py``），本模块只服务运行时异步访问。
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

_PG_PREFIX = "postgresql://"


def to_async_dsn(url: str) -> str:
    """把任意 PostgreSQL 连接串规范化为 asyncpg 方言。"""
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql+psycopg2://"):
        return "postgresql+asyncpg://" + url.split("://", 1)[1]
    if url.startswith(_PG_PREFIX):
        return "postgresql+asyncpg://" + url[len(_PG_PREFIX) :]
    return url


def create_engine(url: str | None = None) -> AsyncEngine:
    """按配置创建异步引擎（测试可注入 url）。"""
    return create_async_engine(
        to_async_dsn(url or settings.DATABASE_URL),
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        pool_timeout=settings.DATABASE_POOL_TIMEOUT,
        pool_recycle=settings.DATABASE_POOL_RECYCLE,
        pool_pre_ping=True,
        echo=False,
    )


engine: AsyncEngine = create_engine()

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI 依赖：每个请求一个会话。

    请求正常完成 → ``commit`` 持久化（服务层只 ``flush``，提交统一在边界）；
    请求抛异常 → ``rollback`` 后继续抛出，交由异常处理器返回统一错误响应。
    """
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()


async def dispose_engine() -> None:
    """应用关闭时释放连接池。"""
    await engine.dispose()
