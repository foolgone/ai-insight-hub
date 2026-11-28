"""RAG 评测数据集 API 集成测试（Phase 1）。

覆盖：
- 数据集创建/列表/详情/重名 409；
- 版本创建（含从已发布版本复制）与发布；
- 导入：成功、逐行错误 + 整批回滚；
- 发布后不可变（PATCH/DELETE/import 全部 409）；
- 权限：viewer 只读、他人数据集 403。
"""
from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from tests.factories import UserFactory, persist

pytestmark = pytest.mark.integration

BASE = "/api/v1/qa-datasets"


def _evidence(text: str = "订单详情页提供申请退款入口。") -> dict[str, Any]:
    return {
        "document_id": "doc-100",
        "chunk_id": "chunk-1",
        "evidence_text": text,
        "page_number": 2,
        "metadata": {"section": "售后"},
    }


def _item(key: str = "Q001", **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "item_key": key,
        "query": "如何申请退款？",
        "gold_answer": "在订单详情页提交退款申请。",
        "gold_evidence": [_evidence()],
        "category": "售后",
        "difficulty": "easy",
        "source": "doc:robot-backend",
        "split": "test",
        "metadata": {"origin": "unit-test"},
    }
    payload.update(overrides)
    return payload


async def _create_dataset(
    client, headers, *, name: str = "机器人后台设置", source_type: str = "doc"
) -> str:
    response = await client.post(
        BASE,
        headers=headers,
        json={"name": name, "description": "Phase 1 测试", "source_type": source_type},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _create_version(client, headers, dataset_id: str, **payload: Any) -> dict[str, Any]:
    response = await client.post(f"{BASE}/{dataset_id}/versions", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def _import(client, headers, dataset_id: str, version_id: str, items: list[dict]) -> Any:
    return await client.post(
        f"{BASE}/{dataset_id}/versions/{version_id}/import",
        headers=headers,
        json={"items": items},
    )


async def test_create_list_and_detail(client, auth_headers) -> None:
    dataset_id = await _create_dataset(client, auth_headers)

    listed = await client.get(BASE, headers=auth_headers)
    assert listed.status_code == 200
    body = listed.json()
    assert body["pagination"]["total"] == 1
    assert body["items"][0]["name"] == "机器人后台设置"

    detail = await client.get(f"{BASE}/{dataset_id}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["versions"] == []


async def test_duplicate_name_conflict(client, auth_headers) -> None:
    await _create_dataset(client, auth_headers, name="重复名字")

    response = await client.post(
        BASE, headers=auth_headers, json={"name": "重复名字", "source_type": "doc"}
    )

    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "QA_DATASET_NAME_EXISTS"


async def test_import_and_read_items(client, auth_headers) -> None:
    dataset_id = await _create_dataset(client, auth_headers)
    version = await _create_version(client, auth_headers, dataset_id)
    assert version["version"] == 1
    assert version["status"] == "draft"

    imported = await _import(
        client, auth_headers, dataset_id, version["id"], [_item("Q001"), _item("Q002")]
    )
    assert imported.status_code == 200, imported.text
    assert imported.json() == {"imported": 2, "version_item_count": 2}

    listed = await client.get(
        f"{BASE}/{dataset_id}/versions/{version['id']}/items", headers=auth_headers
    )
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert [row["item_key"] for row in items] == ["Q001", "Q002"]
    assert items[0]["gold_evidence"][0]["evidence_text"] == "订单详情页提供申请退款入口。"
    # 属性 item_metadata 必须映射回 API 的 metadata
    assert items[0]["metadata"] == {"origin": "unit-test"}

    single = await client.get(
        f"{BASE}/{dataset_id}/versions/{version['id']}/items/{items[0]['id']}",
        headers=auth_headers,
    )
    assert single.status_code == 200
    assert single.json()["query"] == "如何申请退款？"


async def test_import_rejects_bad_rows_with_index_and_rolls_back(client, auth_headers) -> None:
    dataset_id = await _create_dataset(client, auth_headers)
    version = await _create_version(client, auth_headers, dataset_id)

    bad_rows = [
        _item("Q001"),
        _item("Q002", gold_evidence=[{"document_id": "doc-only"}]),
        _item("Q003", split="holdout"),
    ]
    response = await _import(client, auth_headers, dataset_id, version["id"], bad_rows)

    assert response.status_code == 400, response.text
    error = response.json()["error"]
    assert error["code"] == "QA_DATASET_IMPORT_INVALID"
    indexes = {row["index"] for row in error["details"]["errors"]}
    assert indexes == {2, 3}
    assert error["details"]["imported"] == 0

    # 整批回滚：一条都没进库
    listed = await client.get(
        f"{BASE}/{dataset_id}/versions/{version['id']}/items", headers=auth_headers
    )
    assert listed.json()["pagination"]["total"] == 0


async def test_publish_then_immutable(client, auth_headers) -> None:
    dataset_id = await _create_dataset(client, auth_headers)
    version = await _create_version(client, auth_headers, dataset_id)
    await _import(client, auth_headers, dataset_id, version["id"], [_item("Q001")])

    published = await client.post(
        f"{BASE}/{dataset_id}/versions/{version['id']}/publish", headers=auth_headers
    )
    assert published.status_code == 200, published.text
    body = published.json()
    assert body["status"] == "published"
    assert body["item_count"] == 1
    assert len(body["checksum"]) == 64

    items = (
        await client.get(
            f"{BASE}/{dataset_id}/versions/{version['id']}/items", headers=auth_headers
        )
    ).json()["items"]
    item_id = items[0]["id"]

    patch = await client.patch(
        f"{BASE}/{dataset_id}/versions/{version['id']}/items/{item_id}",
        headers=auth_headers,
        json={"query": "改一下"},
    )
    assert patch.status_code == 409
    assert patch.json()["error"]["code"] == "QA_DATASET_IMMUTABLE"

    delete = await client.delete(
        f"{BASE}/{dataset_id}/versions/{version['id']}/items/{item_id}", headers=auth_headers
    )
    assert delete.status_code == 409

    more = await _import(client, auth_headers, dataset_id, version["id"], [_item("Q002")])
    assert more.status_code == 409


async def test_new_version_copy_is_isolated(client, auth_headers) -> None:
    dataset_id = await _create_dataset(client, auth_headers)
    v1 = await _create_version(client, auth_headers, dataset_id)
    await _import(client, auth_headers, dataset_id, v1["id"], [_item("Q001")])
    published = await client.post(
        f"{BASE}/{dataset_id}/versions/{v1['id']}/publish", headers=auth_headers
    )
    assert published.status_code == 200

    v2 = await _create_version(client, auth_headers, dataset_id, from_version_id=v1["id"])
    assert v2["version"] == 2
    assert v2["status"] == "draft"
    assert v2["item_count"] == 1

    # 修改 v2 的条目，v1 不受影响
    v2_items = (
        await client.get(f"{BASE}/{dataset_id}/versions/{v2['id']}/items", headers=auth_headers)
    ).json()["items"]
    patched = await client.patch(
        f"{BASE}/{dataset_id}/versions/{v2['id']}/items/{v2_items[0]['id']}",
        headers=auth_headers,
        json={"gold_answer": "新的答案"},
    )
    assert patched.status_code == 200, patched.text

    v1_items = (
        await client.get(f"{BASE}/{dataset_id}/versions/{v1['id']}/items", headers=auth_headers)
    ).json()["items"]
    assert v1_items[0]["gold_answer"] == "在订单详情页提交退款申请。"

    # v1 的 checksum 未变
    versions = (await client.get(f"{BASE}/{dataset_id}", headers=auth_headers)).json()["versions"]
    by_id = {row["id"]: row for row in versions}
    assert by_id[v1["id"]]["checksum"] == published.json()["checksum"]


async def test_stats_filters_and_keyword(client, auth_headers) -> None:
    dataset_id = await _create_dataset(client, auth_headers)
    version = await _create_version(client, auth_headers, dataset_id)
    await _import(
        client,
        auth_headers,
        dataset_id,
        version["id"],
        [
            _item("Q001", split="train"),
            _item("Q002", split="test", gold_evidence=[]),
            _item("Q003", split="test", category="售前", query="支持哪些支付方式？"),
        ],
    )

    stats = await client.get(
        f"{BASE}/{dataset_id}/stats",
        headers=auth_headers,
        params={"version_id": version["id"]},
    )
    assert stats.status_code == 200, stats.text
    body = stats.json()
    assert body["item_count"] == 3
    assert body["split_counts"] == {"train": 1, "valid": 0, "test": 2}
    assert body["evidence"] == {
        "with_evidence": 2,
        "without_evidence": 1,
        "coverage_rate": 0.6667,
    }
    assert body["category_counts"]["售后"] == 2

    only_test = await client.get(
        f"{BASE}/{dataset_id}/versions/{version['id']}/items",
        headers=auth_headers,
        params={"split": "test"},
    )
    assert only_test.json()["pagination"]["total"] == 2

    keyword = await client.get(
        f"{BASE}/{dataset_id}/versions/{version['id']}/items",
        headers=auth_headers,
        params={"keyword": "支付"},
    )
    assert [row["item_key"] for row in keyword.json()["items"]] == ["Q003"]


async def test_permissions(client, auth_headers, db_session: AsyncSession) -> None:
    dataset_id = await _create_dataset(client, auth_headers)

    viewer = UserFactory(role="viewer", password_hash=hash_password("viewer12345"))
    await persist(db_session, viewer)
    login = await client.post(
        "/api/v1/auth/login", json={"email": viewer.email, "password": "viewer12345"}
    )
    viewer_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    assert (await client.get(BASE, headers=viewer_headers)).status_code == 200
    blocked = await client.post(BASE, headers=viewer_headers, json={"name": "viewer-ds"})
    assert blocked.status_code == 403

    other = UserFactory(password_hash=hash_password("other12345"))
    await persist(db_session, other)
    other_login = await client.post(
        "/api/v1/auth/login", json={"email": other.email, "password": "other12345"}
    )
    other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}

    forbidden = await client.get(f"{BASE}/{dataset_id}", headers=other_headers)
    assert forbidden.status_code == 403


async def test_unknown_dataset_returns_404(client, auth_headers) -> None:
    response = await client.get(f"{BASE}/{uuid.uuid4()}", headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "QA_DATASET_NOT_FOUND"


async def test_publish_empty_version_rejected(client, auth_headers) -> None:
    dataset_id = await _create_dataset(client, auth_headers)
    version = await _create_version(client, auth_headers, dataset_id)

    response = await client.post(
        f"{BASE}/{dataset_id}/versions/{version['id']}/publish", headers=auth_headers
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "QA_DATASET_IMPORT_INVALID"


async def test_import_sample_fixture(client, auth_headers) -> None:
    """仓库内的 20 条脱敏样例必须能直接导入（同时作为导入格式的可执行文档）。"""
    import json
    from pathlib import Path

    fixture = Path(__file__).resolve().parents[1] / "fixtures" / "qa_dataset_sample.json"
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    assert len(payload["items"]) == 20

    dataset_id = await _create_dataset(client, auth_headers, name="脱敏样例集")
    version = await _create_version(client, auth_headers, dataset_id)

    response = await _import(client, auth_headers, dataset_id, version["id"], payload["items"])
    assert response.status_code == 200, response.text
    assert response.json()["imported"] == 20

    stats = await client.get(
        f"{BASE}/{dataset_id}/stats",
        headers=auth_headers,
        params={"version_id": version["id"]},
    )
    body = stats.json()
    assert body["item_count"] == 20
    # 10 条文档类带证据，10 条对话类无证据（与真实 459 条的结构一致）
    assert body["evidence"]["with_evidence"] == 10
    assert body["evidence"]["without_evidence"] == 10
