"""T10：cleaned_data.raw_data_id 数据库外键（ON DELETE CASCADE）集成测试。"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import CleanedData, RawData
from tests.factories import (
    CleanedDataFactory,
    DataSourceFactory,
    RawDataFactory,
    UserFactory,
    persist,
)

pytestmark = pytest.mark.integration


async def _datasource_with_raw(db_session):
    user = UserFactory()
    await persist(db_session, user)
    datasource = DataSourceFactory(user_id=user.id)
    await persist(db_session, datasource)
    raw = RawDataFactory(datasource_id=datasource.id)
    await persist(db_session, raw)
    return datasource, raw


async def test_deleting_raw_data_cascades_cleaned_data(db_session) -> None:
    datasource, raw = await _datasource_with_raw(db_session)
    cleaned = CleanedDataFactory(datasource_id=datasource.id, raw_data_id=raw.id)
    await persist(db_session, cleaned)

    await db_session.delete(raw)
    await db_session.flush()

    remaining = (
        await db_session.execute(select(CleanedData).where(CleanedData.id == cleaned.id))
    ).scalar_one_or_none()
    assert remaining is None, "raw_data 删除后应级联删除 cleaned_data"


async def test_orphan_cleaned_data_rejected(db_session) -> None:
    datasource, _ = await _datasource_with_raw(db_session)
    orphan = CleanedDataFactory(datasource_id=datasource.id, raw_data_id=uuid.uuid4())
    db_session.add(orphan)

    with pytest.raises(IntegrityError):
        await db_session.flush()

    await db_session.rollback()


async def test_cleaned_data_still_works_with_valid_raw(db_session) -> None:
    datasource, raw = await _datasource_with_raw(db_session)
    cleaned = CleanedDataFactory(datasource_id=datasource.id, raw_data_id=raw.id)
    await persist(db_session, cleaned)

    stored = (
        await db_session.execute(select(CleanedData).where(CleanedData.id == cleaned.id))
    ).scalar_one()

    assert stored.raw_data_id == raw.id
    assert isinstance(raw, RawData)
