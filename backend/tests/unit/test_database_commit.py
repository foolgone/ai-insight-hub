"""``get_db`` 事务边界测试：成功提交 / 异常回滚（B-305 回归）。"""
from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from app.core import database

pytestmark = pytest.mark.unit


class _FakeSession:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False
        self.closed = False

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def close(self) -> None:
        self.closed = True

    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()


async def test_get_db_commits_on_success(monkeypatch) -> None:
    session = _FakeSession()
    monkeypatch.setattr(database, "SessionLocal", lambda: session)

    generator: AsyncIterator = database.get_db()
    injected = await anext(generator)
    assert injected is session
    with pytest.raises(StopAsyncIteration):
        await anext(generator)

    assert session.committed is True
    assert session.rolled_back is False


async def test_get_db_rolls_back_on_exception(monkeypatch) -> None:
    session = _FakeSession()
    monkeypatch.setattr(database, "SessionLocal", lambda: session)

    generator = database.get_db()
    await anext(generator)
    with pytest.raises(RuntimeError):
        await generator.athrow(RuntimeError("boom"))

    assert session.committed is False
    assert session.rolled_back is True
