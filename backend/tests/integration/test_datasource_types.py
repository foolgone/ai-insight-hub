"""数据源类型字典 CRUD 集成测试。

覆盖：内置类型播种、创建/改名/删除、code 规则、内置与使用中不可删、
非管理员只读，以及创建/编辑数据源时的类型校验。
"""
from __future__ import annotations

import pytest

from app.core.security import hash_password
from tests.factories import UserFactory, persist

pytestmark = pytest.mark.integration

BASE = "/api/v1/datasource-types"


async def _login(client, email: str, password: str) -> dict[str, str]:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture()
async def admin_headers(client, db_session) -> dict[str, str]:
    admin = UserFactory(password_hash=hash_password("admin12345"), role="admin")
    await persist(db_session, admin)
    return await _login(client, admin.email, "admin12345")


async def _create_type(client, headers, **payload):
    body = {"label": "售后", **payload}
    return await client.post(BASE, json=body, headers=headers)


async def _create_datasource(client, headers, *, name: str, type_code: str):
    return await client.post(
        "/api/v1/datasources",
        json={"name": name, "type": type_code},
        headers=headers,
    )


async def test_seeded_system_types_listed(client, auth_headers) -> None:
    response = await client.get(BASE, headers=auth_headers)
    assert response.status_code == 200, response.text

    items = response.json()["items"]
    codes = {item["code"] for item in items}
    assert {"customer_service", "sales", "support", "other"} <= codes

    seeded = next(item for item in items if item["code"] == "customer_service")
    assert seeded["label"] == "客服对话"
    assert seeded["is_system"] is True
    assert seeded["is_active"] is True
    # 使用量是全局统计（演示库已有数据），这里只校验字段存在且非负
    assert isinstance(seeded["usage_count"], int) and seeded["usage_count"] >= 0
    # 按 sort_order 升序
    assert [item["sort_order"] for item in items] == sorted(
        item["sort_order"] for item in items
    )


async def test_create_update_delete_custom_type(client, admin_headers) -> None:
    created = await _create_type(
        client, admin_headers, label="售后", code="after_sales", description="售后工单"
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["code"] == "after_sales"
    assert body["is_system"] is False
    assert body["usage_count"] == 0

    updated = await client.patch(
        f"{BASE}/{body['id']}", json={"label": "售后服务"}, headers=admin_headers
    )
    assert updated.status_code == 200
    assert updated.json()["label"] == "售后服务"
    assert updated.json()["code"] == "after_sales"

    deleted = await client.delete(f"{BASE}/{body['id']}", headers=admin_headers)
    assert deleted.status_code == 204

    listed = await client.get(BASE, headers=admin_headers)
    assert "after_sales" not in {item["code"] for item in listed.json()["items"]}


async def test_code_auto_generated_when_blank(client, admin_headers) -> None:
    created = await _create_type(client, admin_headers, label="临时类型")
    assert created.status_code == 201, created.text
    assert created.json()["code"].startswith("t_")


async def test_duplicate_code_rejected(client, admin_headers) -> None:
    first = await _create_type(client, admin_headers, label="A", code="dup_code")
    assert first.status_code == 201

    second = await _create_type(client, admin_headers, label="B", code="dup_code")
    assert second.status_code == 400
    assert second.json()["error"]["code"] == "DATASOURCE_TYPE_INVALID"


@pytest.mark.parametrize("code", ["9start", "has space", "a", "x-y"])
async def test_invalid_code_rejected(client, admin_headers, code: str) -> None:
    response = await _create_type(client, admin_headers, label="非法", code=code)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "DATASOURCE_TYPE_INVALID"


async def test_code_is_normalized_to_lowercase(client, admin_headers) -> None:
    response = await _create_type(client, admin_headers, label="大写标识", code="MyType")
    assert response.status_code == 201, response.text
    assert response.json()["code"] == "mytype"


async def test_system_type_cannot_be_deleted(client, admin_headers) -> None:
    listed = await client.get(BASE, headers=admin_headers)
    system = next(item for item in listed.json()["items"] if item["is_system"])

    response = await client.delete(f"{BASE}/{system['id']}", headers=admin_headers)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "DATASOURCE_TYPE_INVALID"


async def test_type_in_use_cannot_be_deleted(client, admin_headers) -> None:
    created = await _create_type(client, admin_headers, label="售后", code="in_use_type")
    type_id = created.json()["id"]

    datasource = await _create_datasource(
        client, admin_headers, name="售后-1月", type_code="in_use_type"
    )
    assert datasource.status_code == 201, datasource.text

    listed = await client.get(BASE, headers=admin_headers)
    usage = next(item for item in listed.json()["items"] if item["id"] == type_id)
    assert usage["usage_count"] == 1

    response = await client.delete(f"{BASE}/{type_id}", headers=admin_headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DATASOURCE_TYPE_IN_USE"
    assert response.json()["error"]["details"]["usage_count"] == 1


async def test_non_admin_cannot_write(client, auth_headers) -> None:
    created = await _create_type(client, auth_headers, label="普通用户创建")
    assert created.status_code == 403

    listed = await client.get(BASE, headers=auth_headers)
    assert listed.status_code == 200


async def test_create_datasource_with_unknown_type_rejected(client, auth_headers) -> None:
    response = await _create_datasource(
        client, auth_headers, name="未知类型", type_code="not_exists"
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "DATASOURCE_TYPE_INVALID"


async def test_inactive_type_not_selectable(client, admin_headers) -> None:
    created = await _create_type(client, admin_headers, label="已停用", code="inactive_type")
    type_id = created.json()["id"]

    disabled = await client.patch(
        f"{BASE}/{type_id}", json={"is_active": False}, headers=admin_headers
    )
    assert disabled.status_code == 200
    assert disabled.json()["is_active"] is False

    # 默认列表不含停用类型；include_inactive=true 才返回
    default_list = await client.get(BASE, headers=admin_headers)
    assert "inactive_type" not in {item["code"] for item in default_list.json()["items"]}
    full_list = await client.get(f"{BASE}?include_inactive=true", headers=admin_headers)
    assert "inactive_type" in {item["code"] for item in full_list.json()["items"]}

    response = await _create_datasource(
        client, admin_headers, name="停用类型", type_code="inactive_type"
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "DATASOURCE_TYPE_INVALID"


async def test_update_datasource_type(client, admin_headers) -> None:
    created = await _create_type(client, admin_headers, label="售后", code="switch_type")
    assert created.status_code == 201

    datasource = await _create_datasource(
        client, admin_headers, name="可切换类型", type_code="other"
    )
    datasource_id = datasource.json()["id"]

    updated = await client.patch(
        f"/api/v1/datasources/{datasource_id}",
        json={"type": "switch_type"},
        headers=admin_headers,
    )
    assert updated.status_code == 200

    detail = await client.get(f"/api/v1/datasources/{datasource_id}", headers=admin_headers)
    assert detail.json()["type"] == "switch_type"

    invalid = await client.patch(
        f"/api/v1/datasources/{datasource_id}",
        json={"type": "not_exists"},
        headers=admin_headers,
    )
    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "DATASOURCE_TYPE_INVALID"


async def test_missing_type_returns_404(client, admin_headers) -> None:
    import uuid

    response = await client.patch(
        f"{BASE}/{uuid.uuid4()}", json={"label": "x"}, headers=admin_headers
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "DATASOURCE_TYPE_NOT_FOUND"
