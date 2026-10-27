"""B-314 cleaned-data API 集成测试。"""
from __future__ import annotations

import uuid
from datetime import datetime

import pytest

from app.core.security import hash_password
from tests.factories import (
    UserFactory,
    persist,
    persist_cleaned,
)

pytestmark = pytest.mark.integration


async def _create_datasource(client, auth_headers) -> str:
    response = await client.post(
        "/api/v1/datasources",
        headers=auth_headers,
        json={"name": "cleaned-api-ds", "type": "customer_service"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _seed_cleaned(db_session, datasource_id: str, **overrides) -> object:
    payload = {
        "timestamp": datetime(2025, 1, 15, 10, 30, 0),
        "quality_score": 90.0,
        "issues": [],
    }
    payload.update(overrides)
    return await persist_cleaned(db_session, uuid.UUID(datasource_id), **payload)


async def test_list_and_detail(client, auth_headers, db_session) -> None:
    datasource_id = await _create_datasource(client, auth_headers)
    item = await _seed_cleaned(db_session, datasource_id, quality_score=95.0)
    await _seed_cleaned(db_session, datasource_id, quality_score=55.0)

    listed = await client.get(
        f"/api/v1/datasources/{datasource_id}/cleaned-data",
        headers=auth_headers,
    )

    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert body["pagination"]["total"] == 2
    assert body["items"][0]["quality_score"] == 95.0
    assert "metadata" in body["items"][0]
    assert "metadata_" not in body["items"][0]
    assert "userMessage" not in body["items"][0]

    detail = await client.get(
        f"/api/v1/datasources/{datasource_id}/cleaned-data/{item.id}",
        headers=auth_headers,
    )
    assert detail.status_code == 200
    detail_body = detail.json()
    assert detail_body["id"] == str(item.id)
    assert detail_body["datasource_id"] == datasource_id
    assert "agent_version" in detail_body


async def test_filters(client, auth_headers, db_session) -> None:
    datasource_id = await _create_datasource(client, auth_headers)
    await _seed_cleaned(db_session, datasource_id, quality_score=95.0, issues=[])
    await _seed_cleaned(db_session, datasource_id, quality_score=55.0, issues=["x"])
    await _seed_cleaned(db_session, datasource_id, quality_score=75.0, issues=[])

    high = await client.get(
        f"/api/v1/datasources/{datasource_id}/cleaned-data",
        headers=auth_headers,
        params={"quality_score_min": 60},
    )
    assert high.json()["pagination"]["total"] == 2

    with_issues = await client.get(
        f"/api/v1/datasources/{datasource_id}/cleaned-data",
        headers=auth_headers,
        params={"has_issues": True},
    )
    assert with_issues.json()["pagination"]["total"] == 1

    without_issues = await client.get(
        f"/api/v1/datasources/{datasource_id}/cleaned-data",
        headers=auth_headers,
        params={"has_issues": False},
    )
    assert without_issues.json()["pagination"]["total"] == 2


async def test_detail_not_found(client, auth_headers) -> None:
    datasource_id = await _create_datasource(client, auth_headers)

    response = await client.get(
        f"/api/v1/datasources/{datasource_id}/cleaned-data/{uuid.uuid4()}",
        headers=auth_headers,
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CLEANED_DATA_NOT_FOUND"


async def test_other_user_forbidden(client, auth_headers, db_session) -> None:
    datasource_id = await _create_datasource(client, auth_headers)
    other = UserFactory(password_hash=hash_password("other12345"))
    await persist(db_session, other)
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": other.email, "password": "other12345"},
    )
    token = login.json()["access_token"]

    response = await client.get(
        f"/api/v1/datasources/{datasource_id}/cleaned-data",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "AUTH_FORBIDDEN"
