"""B-301 数据源 service 层测试（直接调用，覆盖配额/软删/硬删等分支）。"""
from __future__ import annotations

import uuid

import pytest

from app.api.pagination import PaginationParams
from app.core.exceptions import DataSourceNotFoundError, DataSourceQuotaExceededError
from app.schemas.datasource import DataSourceCreate, DataSourceUpdate
from app.services import datasource_service
from tests.factories import RawDataFactory, UserFactory, persist

pytestmark = pytest.mark.integration


def _create_payload(**overrides) -> DataSourceCreate:
    data = {"name": "service-source", "type": "customer_service"}
    data.update(overrides)
    return DataSourceCreate(**data)


async def test_create_list_get_update_delete_flow(db_session) -> None:
    user = UserFactory()
    await persist(db_session, user)

    created = await datasource_service.create(db_session, user=user, data=_create_payload())
    rows, page = await datasource_service.list_datasources(
        db_session, user=user, params=PaginationParams(page=1, limit=10)
    )
    assert page.total == 1 and rows[0].id == created.id

    fetched = await datasource_service.get(db_session, user=user, datasource_id=created.id)
    assert fetched.id == created.id

    updated = await datasource_service.update(
        db_session,
        user=user,
        datasource_id=created.id,
        data=DataSourceUpdate(name="renamed", description="desc"),
    )
    assert updated.name == "renamed"
    assert updated.description == "desc"

    message, deleted = await datasource_service.delete(
        db_session, user=user, datasource_id=created.id
    )
    assert message == "Data source deleted successfully"
    assert deleted == 0

    with pytest.raises(DataSourceNotFoundError):
        await datasource_service.get(db_session, user=user, datasource_id=created.id)


async def test_quota_exceeded_branch(db_session) -> None:
    user = UserFactory(quota={"max_datasources": 0})
    await persist(db_session, user)

    with pytest.raises(DataSourceQuotaExceededError):
        await datasource_service.create(db_session, user=user, data=_create_payload())


async def test_invalid_quota_falls_back_to_default(db_session) -> None:
    user = UserFactory(quota={"max_datasources": "not-a-number"})
    await persist(db_session, user)

    created = await datasource_service.create(db_session, user=user, data=_create_payload())

    assert created.id is not None


async def test_force_delete_counts_related_records(db_session) -> None:
    user = UserFactory()
    await persist(db_session, user)
    datasource = await datasource_service.create(db_session, user=user, data=_create_payload())
    await persist(db_session, RawDataFactory(datasource_id=datasource.id))

    _, deleted = await datasource_service.delete(
        db_session, user=user, datasource_id=datasource.id, force=True
    )

    assert deleted >= 1


async def test_get_missing_raises_not_found(db_session) -> None:
    user = UserFactory()
    await persist(db_session, user)

    with pytest.raises(DataSourceNotFoundError):
        await datasource_service.get(db_session, user=user, datasource_id=uuid.uuid4())
