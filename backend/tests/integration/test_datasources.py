"""B-301 数据源 CRUD / 配额 / 归属集成测试。"""
from __future__ import annotations

import uuid

import pytest

from app.core.security import hash_password
from app.models import DataSource
from tests.factories import DataSourceFactory, RawDataFactory, UserFactory, persist

pytestmark = pytest.mark.integration

EVALUATION_DIMENSIONS = [
    "accuracy",
    "completeness",
    "tone",
    "compliance",
    "hallucination",
]


def _payload(**overrides) -> dict:
    data = {
        "name": "客服对话-2025年1月",
        "description": "2025年1月的客服对话数据",
        "type": "customer_service",
    }
    data.update(overrides)
    return data


async def _create(client, auth_headers, **overrides) -> dict:
    response = await client.post(
        "/api/v1/datasources", headers=auth_headers, json=_payload(**overrides)
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _login(client, email: str, password: str) -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


async def test_create_datasource_returns_defaults(client, auth_headers) -> None:
    body = await _create(client, auth_headers)

    assert body["name"] == "客服对话-2025年1月"
    assert body["status"] == "active"
    assert body["config"]["evaluation_dimensions"] == EVALUATION_DIMENSIONS
    assert body["config"]["auto_clean"] is True
    assert body["statistics"]["total_records"] == 0
    assert body["created_at"]
    assert "workflowStatus" not in body


async def test_create_rejects_invalid_type(client, auth_headers) -> None:
    response = await client.post(
        "/api/v1/datasources",
        headers=auth_headers,
        json=_payload(type="unknown"),
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_create_rejects_invalid_dimensions(client, auth_headers) -> None:
    response = await client.post(
        "/api/v1/datasources",
        headers=auth_headers,
        json=_payload(config={"evaluation_dimensions": ["accuracy", "bogus"]}),
    )

    assert response.status_code == 422


async def test_list_filters_and_pagination(client, auth_headers) -> None:
    await _create(client, auth_headers, name="source-a", type="customer_service")
    await _create(client, auth_headers, name="source-b", type="sales")

    response = await client.get(
        "/api/v1/datasources",
        headers=auth_headers,
        params={"page": 1, "limit": 1, "type": "sales", "sort": "-created_at"},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["name"] == "source-b"
    assert body["pagination"] == {
        "page": 1,
        "limit": 1,
        "total": 1,
        "pages": 1,
        "has_next": False,
        "has_prev": False,
    }


async def test_get_update_and_soft_delete(client, auth_headers) -> None:
    created = await _create(client, auth_headers)
    datasource_id = created["id"]

    detail = await client.get(f"/api/v1/datasources/{datasource_id}", headers=auth_headers)
    assert detail.status_code == 200

    updated = await client.patch(
        f"/api/v1/datasources/{datasource_id}",
        headers=auth_headers,
        json={"name": "新名称", "config": {"auto_clean": False}},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "新名称"

    refreshed = await client.get(f"/api/v1/datasources/{datasource_id}", headers=auth_headers)
    config = refreshed.json()["config"]
    assert config["auto_clean"] is False
    assert config["auto_evaluate"] is True  # 局部更新保留未传字段

    deleted = await client.delete(f"/api/v1/datasources/{datasource_id}", headers=auth_headers)
    assert deleted.status_code == 200
    assert deleted.json()["message"] == "Data source deleted successfully"

    gone = await client.get(f"/api/v1/datasources/{datasource_id}", headers=auth_headers)
    assert gone.status_code == 404
    assert gone.json()["error"]["code"] == "DATASOURCE_NOT_FOUND"


async def test_force_delete_counts_related_records(
    client, auth_headers, db_session, test_user
) -> None:
    created = await _create(client, auth_headers)
    datasource = await db_session.get(DataSource, uuid.UUID(created["id"]))
    raw = RawDataFactory(datasource_id=datasource.id)
    await persist(db_session, raw)

    response = await client.delete(
        f"/api/v1/datasources/{created['id']}",
        headers=auth_headers,
        params={"force": "true"},
    )

    assert response.status_code == 200
    assert response.json()["deleted_records"] >= 1

    gone = await client.get(f"/api/v1/datasources/{created['id']}", headers=auth_headers)
    assert gone.status_code == 404


async def test_quota_exceeded(client, auth_headers, db_session, test_user) -> None:
    test_user.quota = {"max_datasources": 1, "max_monthly_records": 0, "max_monthly_tokens": 0}
    await db_session.flush()
    await _create(client, auth_headers)

    response = await client.post(
        "/api/v1/datasources", headers=auth_headers, json=_payload(name="second")
    )

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "DATASOURCE_QUOTA_EXCEEDED"


async def test_other_user_cannot_access(client, auth_headers, db_session) -> None:
    created = await _create(client, auth_headers)
    other = UserFactory(password_hash=hash_password("other12345"))
    await persist(db_session, other)
    other_token = await _login(client, other.email, "other12345")

    response = await client.get(
        f"/api/v1/datasources/{created['id']}",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "AUTH_FORBIDDEN"


async def test_viewer_cannot_create(client, db_session) -> None:
    viewer = UserFactory(password_hash=hash_password("viewer123"), role="viewer")
    await persist(db_session, viewer)
    token = await _login(client, viewer.email, "viewer123")

    response = await client.post(
        "/api/v1/datasources",
        headers={"Authorization": f"Bearer {token}"},
        json=_payload(),
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "AUTH_FORBIDDEN"


async def test_factory_created_datasource_is_listed(
    client, auth_headers, db_session, test_user
) -> None:
    datasource = DataSourceFactory(user_id=test_user.id, name="factory-source")
    await persist(db_session, datasource)

    response = await client.get("/api/v1/datasources", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["pagination"]["total"] == 1


async def test_admin_sees_and_reads_all_datasources(
    client, auth_headers, db_session, test_user
) -> None:
    created = await _create(client, auth_headers)
    admin = UserFactory(password_hash=hash_password("admin12345"), role="admin")
    await persist(db_session, admin)
    admin_token = await _login(client, admin.email, "admin12345")
    headers = {"Authorization": f"Bearer {admin_token}"}

    listed = await client.get("/api/v1/datasources", headers=headers)
    assert listed.json()["pagination"]["total"] >= 1

    detail = await client.get(f"/api/v1/datasources/{created['id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["id"] == created["id"]


async def test_update_description_field(client, auth_headers) -> None:
    created = await _create(client, auth_headers)

    response = await client.patch(
        f"/api/v1/datasources/{created['id']}",
        headers=auth_headers,
        json={"description": "更新后的描述"},
    )

    assert response.status_code == 200
    assert response.json()["description"] == "更新后的描述"


async def test_delete_missing_datasource_returns_404(client, auth_headers) -> None:
    response = await client.delete(
        "/api/v1/datasources/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "DATASOURCE_NOT_FOUND"


async def test_api_layer_calls_service_layer(client, auth_headers, monkeypatch) -> None:
    from app.services import datasource_service

    called: dict[str, bool] = {}
    original = datasource_service.create

    async def spy(*args, **kwargs):
        called["yes"] = True
        return await original(*args, **kwargs)

    monkeypatch.setattr(datasource_service, "create", spy)

    response = await client.post("/api/v1/datasources", headers=auth_headers, json=_payload())

    assert response.status_code == 201
    assert called.get("yes") is True
