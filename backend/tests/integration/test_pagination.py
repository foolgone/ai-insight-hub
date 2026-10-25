"""B-211 分页 / 排序集成测试。"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.api.pagination import PaginationParams, paginate
from app.models import DataSource
from tests.factories import DataSourceFactory, UserFactory, persist

pytestmark = pytest.mark.integration


async def _seed(db_session) -> object:
    user = UserFactory()
    await persist(db_session, user)
    for name in ("b-source", "a-source", "c-source"):
        await persist(db_session, DataSourceFactory(user_id=user.id, name=name))
    return user


async def test_pagination_and_ascending_sort(db_session) -> None:
    user = await _seed(db_session)
    stmt = select(DataSource).where(DataSource.user_id == user.id)

    items, page = await paginate(
        db_session,
        stmt,
        PaginationParams(page=1, limit=2, sort="name"),
        sortable={"name": DataSource.name, "created_at": DataSource.created_at},
    )

    assert [item.name for item in items] == ["a-source", "b-source"]
    assert page.total == 3
    assert page.pages == 2
    assert page.has_next is True
    assert page.has_prev is False


async def test_pagination_second_page_descending_sort(db_session) -> None:
    user = await _seed(db_session)
    stmt = select(DataSource).where(DataSource.user_id == user.id)

    items, page = await paginate(
        db_session,
        stmt,
        PaginationParams(page=2, limit=2, sort="-name"),
        sortable={"name": DataSource.name},
    )

    assert [item.name for item in items] == ["a-source"]
    assert page.has_next is False
    assert page.has_prev is True


async def test_unknown_sort_field_is_ignored(db_session) -> None:
    user = await _seed(db_session)
    stmt = select(DataSource).where(DataSource.user_id == user.id)

    items, page = await paginate(
        db_session,
        stmt,
        PaginationParams(page=1, limit=10, sort="password_hash"),
        sortable={"name": DataSource.name},
    )

    assert len(items) == 3
    assert page.total == 3
