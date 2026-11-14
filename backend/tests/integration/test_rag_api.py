"""RAG 执行与 Trace API 集成测试（Phase 2）。

全部使用 ``mock`` 适配器（``RAG_ADAPTER`` 默认值），不访问外部服务。
覆盖：检索/问答两种模式、数据集条目联动、失败 trace、幂等、权限、404、健康检查。
"""
from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models import RagTrace
from app.ports.rag import RAGResult
from app.services.rag import execute as rag_execute
from app.services.rag.mock import MockRAGAdapter
from tests.factories import UserFactory, persist

pytestmark = pytest.mark.integration

BASE = "/api/v1/rag"


class _FailingAdapter:
    """固定失败适配器（模拟外部服务不可用）。"""

    name = "mock"

    async def retrieve(self, query: str, *, config=None) -> RAGResult:  # noqa: ANN001
        raise RuntimeError("upstream timeout")

    async def query(self, query: str, *, config=None) -> RAGResult:  # noqa: ANN001
        raise RuntimeError("upstream timeout")

    async def health_check(self) -> bool:
        return False

    async def aclose(self) -> None:
        return None


async def _run(client, headers, *, mode: str = "query", **payload: Any) -> dict[str, Any]:
    body = {"query": "怎么退款？", "mode": mode, **payload}
    response = await client.post(f"{BASE}/queries", headers=headers, json=body)
    return response


async def test_retrieve_mode_records_trace(client, auth_headers) -> None:
    response = await _run(client, auth_headers, mode="retrieve")

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["adapter"] == "mock"
    assert body["execution_mode"] == "retrieve"
    assert body["context_source"] == "hybrid_search"
    assert body["context_available"] is True
    assert body["execution_status"] == "success"
    assert len(body["retrieved_contexts"]) == 3
    assert body["retrieved_scores"][0] == 0.92
    assert "token_usage" in body["missing"]
    assert body["answer"] is None

    trace_id = body["trace_id"]
    detail = await client.get(f"{BASE}/traces/{trace_id}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["query"] == "怎么退款？"
    assert detail.json()["retrieved_contexts"][0]["document_id"] == "mock-doc-approval"

    listed = await client.get(f"{BASE}/traces", headers=auth_headers)
    assert listed.status_code == 200
    page = listed.json()
    assert page["pagination"]["total"] == 1
    assert page["items"][0]["context_count"] == 3
    assert page["items"][0]["trace_id"] == trace_id


async def test_query_mode_returns_answer(client, auth_headers) -> None:
    response = await _run(client, auth_headers, mode="query")

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["execution_mode"] == "query"
    assert body["context_source"] == "agent_chat"
    assert body["answer"] is not None
    assert body["context_available"] is True


async def test_run_with_dataset_item(client, auth_headers) -> None:
    dataset = await client.post(
        "/api/v1/qa-datasets",
        headers=auth_headers,
        json={"name": "trace-link", "source_type": "doc"},
    )
    dataset_id = dataset.json()["id"]
    version = await client.post(
        f"/api/v1/qa-datasets/{dataset_id}/versions", headers=auth_headers, json={}
    )
    version_id = version.json()["id"]
    imported = await client.post(
        f"/api/v1/qa-datasets/{dataset_id}/versions/{version_id}/import",
        headers=auth_headers,
        json={
            "items": [
                {
                    "item_key": "Q001",
                    "query": "数据集里的问题",
                    "gold_answer": "标准答案",
                    "gold_evidence": [],
                }
            ]
        },
    )
    assert imported.status_code == 200, imported.text
    items = await client.get(
        f"/api/v1/qa-datasets/{dataset_id}/versions/{version_id}/items",
        headers=auth_headers,
    )
    item_id = items.json()["items"][0]["id"]

    response = await client.post(
        f"{BASE}/queries",
        headers=auth_headers,
        json={"dataset_item_id": item_id, "mode": "retrieve"},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["query"] == "数据集里的问题"
    assert body["dataset_item_id"] == item_id


async def test_failed_adapter_is_persisted(client, auth_headers, monkeypatch) -> None:
    monkeypatch.setattr("app.api.v1.rag.build_adapter", lambda name=None: _FailingAdapter())

    response = await _run(client, auth_headers, mode="query")

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["execution_status"] == "failed"
    assert body["context_available"] is False
    assert "upstream timeout" in (body["error_message"] or "")
    assert body["missing"] == ["retrieved_contexts", "token_usage"]

    detail = await client.get(f"{BASE}/traces/{body['trace_id']}", headers=auth_headers)
    assert detail.json()["execution_status"] == "failed"


async def test_idempotent_execution_reuses_trace(db_session: AsyncSession, test_user) -> None:
    adapter = MockRAGAdapter()
    first = await rag_execute.execute_query(
        db_session,
        user=test_user,
        adapter=adapter,
        query="幂等问题",
        mode="retrieve",
        idempotency_key="task:t1:item:i1",
    )
    second = await rag_execute.execute_query(
        db_session,
        user=test_user,
        adapter=adapter,
        query="幂等问题",
        mode="retrieve",
        idempotency_key="task:t1:item:i1",
    )

    assert first.id == second.id
    total = await db_session.scalar(select(func.count()).select_from(RagTrace))
    assert total == 1


async def test_trace_not_found(client, auth_headers) -> None:
    response = await client.get(f"{BASE}/traces/{uuid.uuid4()}", headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RAG_TRACE_NOT_FOUND"


async def test_permissions(client, auth_headers, db_session: AsyncSession) -> None:
    created = await _run(client, auth_headers, mode="retrieve")
    trace_id = created.json()["trace_id"]

    viewer = UserFactory(role="viewer", password_hash=hash_password("viewer12345"))
    await persist(db_session, viewer)
    login = await client.post(
        "/api/v1/auth/login", json={"email": viewer.email, "password": "viewer12345"}
    )
    viewer_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    blocked = await client.post(
        f"{BASE}/queries", headers=viewer_headers, json={"query": "x", "mode": "retrieve"}
    )
    assert blocked.status_code == 403

    other = UserFactory(password_hash=hash_password("other12345"))
    await persist(db_session, other)
    other_login = await client.post(
        "/api/v1/auth/login", json={"email": other.email, "password": "other12345"}
    )
    other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}

    forbidden = await client.get(f"{BASE}/traces/{trace_id}", headers=other_headers)
    assert forbidden.status_code == 403


async def test_health_reports_unconfigured_weknora(client, auth_headers, monkeypatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "WEKNORA_BASE_URL", "")
    monkeypatch.setattr(settings, "WEKNORA_API_KEY", "")

    response = await client.get(
        f"{BASE}/health", headers=auth_headers, params={"adapter": "weknora"}
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["adapter"] == "weknora"
    assert body["configured"] is False
    assert body["healthy"] is False
    assert set(body["missing"]) == {"WEKNORA_BASE_URL", "WEKNORA_API_KEY"}


async def test_unknown_adapter_rejected(client, auth_headers) -> None:
    response = await client.post(
        f"{BASE}/queries",
        headers=auth_headers,
        json={"query": "x", "mode": "retrieve", "adapter": "nope"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "BAD_REQUEST"


async def test_adapter_health(client, auth_headers) -> None:
    response = await client.get(f"{BASE}/health", headers=auth_headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["adapter"] == "mock"
    assert body["healthy"] is True
    assert body["configured"] is True
