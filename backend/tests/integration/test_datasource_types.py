"""数据源类型字典集成测试（按用户隔离，多租户）。

覆盖：默认类型按用户播种、跨用户不可见/不可改、同 code 可各自存在、
默认与使用中不可删、最后一个启用类型保护、viewer 只读，
以及创建/编辑数据源时的类型归属校验。
"""
from __future__ import annotations

import pytest

from app.core.security import hash_password
from tests.factories import UserFactory, persist

pytestmark = pytest.mark.integration

BASE = "/api/v1/datasource-types"
DEFAULT_CODES = {"customer_service", "sales", "support", "other"}


async def _login(client, email: str, password: str) -> dict[str, str]:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def _make_user_headers(client, db_session, *, role: str = "user", password: str = "user12345"):
    user = UserFactory(password_hash=hash_password(password), role=role)
    await persist(db_session, user)
    headers = await _login(client, user.email, password)
    return user, headers


@pytest.fixture()
async def admin_headers(client, db_session) -> dict[str, str]:
    _, headers = await _make_user_headers(client, db_session, role="admin", password="admin12345")
    return headers


@pytest.fixture()
async def second_user_headers(client, db_session) -> dict[str, str]:
    _, headers = await _make_user_headers(client, db_session, role="user", password="other12345")
    return headers


@pytest.fixture()
async def viewer_headers(client, db_session) -> dict[str, str]:
    _, headers = await _make_user_headers(client, db_session, role="viewer", password="viewer12345")
    return headers


async def _list(client, headers, *, include_inactive: bool = False):
    query = "?include_inactive=true" if include_inactive else ""
    response = await client.get(f"{BASE}{query}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["items"]


async def _create_type(client, headers, **payload):
    body = {"label": "售后", **payload}
    return await client.post(BASE, json=body, headers=headers)


async def _create_datasource(client, headers, *, name: str, type_code: str):
    return await client.post(
        "/api/v1/datasources",
        json={"name": name, "type": type_code},
        headers=headers,
    )


async def test_defaults_provisioned_per_user(
    client, auth_headers, second_user_headers
) -> None:
    first = await _list(client, auth_headers)
    assert {item["code"] for item in first} == DEFAULT_CODES
    assert all(item["is_system"] is True for item in first)
    assert all(item["usage_count"] == 0 for item in first)

    second = await _list(client, second_user_headers)
    assert {item["code"] for item in second} == DEFAULT_CODES
    # 两套默认类型是各自独立的数据行
    assert {item["id"] for item in first}.isdisjoint({item["id"] for item in second})


async def test_create_update_delete_custom_type(client, auth_headers) -> None:
    created = await _create_type(
        client, auth_headers, label="售后", code="after_sales", description="售后工单"
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["code"] == "after_sales"
    assert body["is_system"] is False
    assert body["usage_count"] == 0

    updated = await client.patch(
        f"{BASE}/{body['id']}", json={"label": "售后服务"}, headers=auth_headers
    )
    assert updated.status_code == 200
    assert updated.json()["label"] == "售后服务"
    assert updated.json()["code"] == "after_sales"

    deleted = await client.delete(f"{BASE}/{body['id']}", headers=auth_headers)
    assert deleted.status_code == 204

    assert "after_sales" not in {item["code"] for item in await _list(client, auth_headers)}


async def test_types_are_isolated_between_users(
    client, auth_headers, second_user_headers
) -> None:
    created = await _create_type(client, auth_headers, label="售后", code="after_sales")
    type_id = created.json()["id"]

    # 对方列表看不到
    other_codes = {item["code"] for item in await _list(client, second_user_headers)}
    assert "after_sales" not in other_codes

    # 对方按 id 访问/修改/删除 → 一律 404（不暴露存在性）
    for method, path, payload in (
        ("patch", f"{BASE}/{type_id}", {"label": "越权"}),
        ("delete", f"{BASE}/{type_id}", None),
    ):
        if method == "patch":
            response = await client.patch(path, json=payload, headers=second_user_headers)
        else:
            response = await client.delete(path, headers=second_user_headers)
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "DATASOURCE_TYPE_NOT_FOUND"

    # 原用户仍然可见且未被改动
    mine = {item["id"]: item for item in await _list(client, auth_headers)}
    assert mine[type_id]["label"] == "售后"


async def test_same_code_allowed_across_users(
    client, auth_headers, second_user_headers
) -> None:
    first = await _create_type(client, auth_headers, label="售后A", code="shared_code")
    second = await _create_type(client, second_user_headers, label="售后B", code="shared_code")
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["label"] == "售后A"
    assert second.json()["label"] == "售后B"


async def test_duplicate_code_rejected_within_user(client, auth_headers) -> None:
    assert (await _create_type(client, auth_headers, label="A", code="dup_code")).status_code == 201
    second = await _create_type(client, auth_headers, label="B", code="dup_code")
    assert second.status_code == 400
    assert second.json()["error"]["code"] == "DATASOURCE_TYPE_INVALID"


async def test_code_auto_generated_when_blank(client, auth_headers) -> None:
    created = await _create_type(client, auth_headers, label="临时类型")
    assert created.status_code == 201
    assert created.json()["code"].startswith("t_")


@pytest.mark.parametrize("code", ["9start", "has space", "a", "x-y"])
async def test_invalid_code_rejected(client, auth_headers, code: str) -> None:
    response = await _create_type(client, auth_headers, label="非法", code=code)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "DATASOURCE_TYPE_INVALID"


async def test_code_is_normalized_to_lowercase(client, auth_headers) -> None:
    response = await _create_type(client, auth_headers, label="大写标识", code="MyType")
    assert response.status_code == 201
    assert response.json()["code"] == "mytype"


async def test_default_type_cannot_be_deleted(client, auth_headers) -> None:
    default = next(item for item in await _list(client, auth_headers) if item["is_system"])
    response = await client.delete(f"{BASE}/{default['id']}", headers=auth_headers)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "DATASOURCE_TYPE_INVALID"


async def test_type_in_use_cannot_be_deleted(client, auth_headers) -> None:
    created = await _create_type(client, auth_headers, label="售后", code="in_use_type")
    type_id = created.json()["id"]

    datasource = await _create_datasource(
        client, auth_headers, name="售后-1月", type_code="in_use_type"
    )
    assert datasource.status_code == 201, datasource.text

    listed = await _list(client, auth_headers)
    usage = next(item for item in listed if item["id"] == type_id)
    assert usage["usage_count"] == 1

    response = await client.delete(f"{BASE}/{type_id}", headers=auth_headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DATASOURCE_TYPE_IN_USE"
    assert response.json()["error"]["details"]["usage_count"] == 1


async def test_usage_count_is_owner_scoped(
    client, auth_headers, second_user_headers
) -> None:
    """A 的数据源不会计入 B 同名类型的 usage_count。"""
    assert (await _create_type(client, auth_headers, label="A", code="scoped_code")).status_code == 201
    assert (
        await _create_type(client, second_user_headers, label="B", code="scoped_code")
    ).status_code == 201

    created = await _create_datasource(
        client, auth_headers, name="A 的数据源", type_code="scoped_code"
    )
    assert created.status_code == 201

    a_usage = next(
        item["usage_count"]
        for item in await _list(client, auth_headers)
        if item["code"] == "scoped_code"
    )
    b_usage = next(
        item["usage_count"]
        for item in await _list(client, second_user_headers)
        if item["code"] == "scoped_code"
    )
    assert a_usage == 1
    assert b_usage == 0


async def test_cannot_deactivate_last_active_type(client, auth_headers) -> None:
    items = await _list(client, auth_headers)
    assert len(items) == 4

    for item in items[:3]:
        response = await client.patch(
            f"{BASE}/{item['id']}", json={"is_active": False}, headers=auth_headers
        )
        assert response.status_code == 200

    last = items[3]
    response = await client.patch(
        f"{BASE}/{last['id']}", json={"is_active": False}, headers=auth_headers
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "DATASOURCE_TYPE_INVALID"


async def test_viewer_cannot_write(client, viewer_headers) -> None:
    created = await _create_type(client, viewer_headers, label="只读用户创建")
    assert created.status_code == 403

    # 只读用户仍可读自己的类型
    assert len(await _list(client, viewer_headers)) == 4


async def test_create_datasource_with_unknown_type_rejected(client, auth_headers) -> None:
    response = await _create_datasource(
        client, auth_headers, name="未知类型", type_code="not_exists"
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "DATASOURCE_TYPE_INVALID"


async def test_other_users_type_cannot_be_used_for_datasource(
    client, auth_headers, second_user_headers
) -> None:
    """A 自建的类型，B 不能拿来建自己的数据源。"""
    await _create_type(client, auth_headers, label="A 私有", code="a_private_type")

    response = await _create_datasource(
        client, second_user_headers, name="越权类型", type_code="a_private_type"
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "DATASOURCE_TYPE_INVALID"


async def test_inactive_type_not_selectable(client, auth_headers) -> None:
    created = await _create_type(client, auth_headers, label="已停用", code="inactive_type")
    type_id = created.json()["id"]

    disabled = await client.patch(
        f"{BASE}/{type_id}", json={"is_active": False}, headers=auth_headers
    )
    assert disabled.status_code == 200
    assert disabled.json()["is_active"] is False

    default_list = await _list(client, auth_headers)
    assert "inactive_type" not in {item["code"] for item in default_list}
    full_list = await _list(client, auth_headers, include_inactive=True)
    assert "inactive_type" in {item["code"] for item in full_list}

    response = await _create_datasource(
        client, auth_headers, name="停用类型", type_code="inactive_type"
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "DATASOURCE_TYPE_INVALID"


async def test_update_datasource_type(client, auth_headers) -> None:
    created = await _create_type(client, auth_headers, label="售后", code="switch_type")
    assert created.status_code == 201

    datasource = await _create_datasource(
        client, auth_headers, name="可切换类型", type_code="other"
    )
    datasource_id = datasource.json()["id"]

    updated = await client.patch(
        f"/api/v1/datasources/{datasource_id}",
        json={"type": "switch_type"},
        headers=auth_headers,
    )
    assert updated.status_code == 200

    detail = await client.get(f"/api/v1/datasources/{datasource_id}", headers=auth_headers)
    assert detail.json()["type"] == "switch_type"

    invalid = await client.patch(
        f"/api/v1/datasources/{datasource_id}",
        json={"type": "not_exists"},
        headers=auth_headers,
    )
    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "DATASOURCE_TYPE_INVALID"


async def test_missing_type_returns_404(client, auth_headers) -> None:
    import uuid

    response = await client.patch(
        f"{BASE}/{uuid.uuid4()}", json={"label": "x"}, headers=auth_headers
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "DATASOURCE_TYPE_NOT_FOUND"
