"""B-506 / B-507 知识库服务与 API 集成测试。"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.agents.base import AgentResult
from app.models import KnowledgeBase
from app.services import knowledge_service
from tests.factories import (
    CleanedDataFactory,
    DataSourceFactory,
    KnowledgeBaseFactory,
    RawDataFactory,
    TaskFactory,
    UserFactory,
    persist,
)

pytestmark = pytest.mark.integration

_FAQS = [
    {
        "question": "iPhone 14 多少钱？",
        "answer": "5999 元起。",
        "category": "价格",
        "variations": ["iPhone 14 价格"],
        "confidence": 0.95,
        "source_dialogue_ids": [],
        "embedding": [0.1] * 384,
    },
    {
        "question": "多久发货？",
        "answer": "48 小时内发出。",
        "category": "物流",
        "variations": [],
        "confidence": 0.9,
        "source_dialogue_ids": [],
        "embedding": [0.2] * 384,
    },
]

_GAPS = [
    {"question": "能否开发票？", "frequency": 12, "category": "发票"},
    {"question": "支持货到付款吗？", "frequency": 2, "category": "支付"},
]


class _FakeAgent:
    def __init__(self, result: AgentResult) -> None:
        self._result = result

    async def extract(self, input_data, **kwargs) -> AgentResult:
        return self._result


def _success_result() -> AgentResult:
    return AgentResult(
        success=True,
        data={
            "datasource_id": str(uuid.uuid4()),
            "faqs": _FAQS,
            "gaps": _GAPS,
            "stats": {"kept": 2},
        },
        metadata={"agent": "extraction_agent", "version": "v1.0.0"},
        duration=1.0,
        token_usage={"input": 100, "output": 50},
    )


async def _setup(db_session) -> tuple:
    user = UserFactory()
    await persist(db_session, user)
    datasource = DataSourceFactory(user_id=user.id)
    await persist(db_session, datasource)
    raw = RawDataFactory(datasource_id=datasource.id)
    await persist(db_session, raw)
    await persist(
        db_session,
        CleanedDataFactory(
            datasource_id=datasource.id,
            raw_data_id=raw.id,
            user_message="iPhone 14 多少钱",
            ai_response="5999 元起",
        ),
    )
    # 冷启动种子（12 条）应在提取后被替换
    for index in range(12):
        await persist(
            db_session,
            KnowledgeBaseFactory(
                datasource_id=datasource.id,
                source="seed",
                is_seed=True,
                question=f"种子问题 {index}",
            ),
        )
    task = TaskFactory(
        user_id=user.id,
        datasource_id=datasource.id,
        task_type="extract",
        status="pending",
        params={"max_faq_count": 100},
    )
    await persist(db_session, task)
    return user, datasource, task


async def test_run_extraction_replaces_seed_and_saves_gaps(db_session, monkeypatch) -> None:
    _, datasource, task = await _setup(db_session)
    monkeypatch.setattr(knowledge_service, "_build_agent", lambda: _FakeAgent(_success_result()))
    monkeypatch.setattr(
        knowledge_service,
        "enqueue_extract",
        lambda task: "celery-knowledge",
    )

    outcome = await knowledge_service.run_extraction_task(str(task.id), session=db_session)

    assert outcome["status"] == "completed"
    assert outcome["faqs_inserted"] == 2

    rows = (
        (
            await db_session.execute(
                select(KnowledgeBase).where(KnowledgeBase.datasource_id == datasource.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 2
    assert all(row.source == "extracted" and not row.is_seed for row in rows)

    await db_session.refresh(task)
    assert task.result["gaps_count"] == 2
    assert task.result["seed_removed"] == 12
    assert task.result["faqs_inserted"] == 2

    await db_session.refresh(datasource)
    assert datasource.workflow_status in {"knowledge_built", "ready"}


async def test_extract_endpoint_returns_202(client, auth_headers, monkeypatch) -> None:
    response = await client.post(
        "/api/v1/datasources",
        headers=auth_headers,
        json={"name": "knowledge-extract-ds", "type": "customer_service"},
    )
    datasource_id = response.json()["id"]
    monkeypatch.setattr(knowledge_service, "enqueue_extract", lambda task: "celery-knowledge")

    submitted = await client.post(
        f"/api/v1/datasources/{datasource_id}/extract-knowledge",
        headers=auth_headers,
    )

    assert submitted.status_code == 202, submitted.text
    assert submitted.json()["task_id"]


async def test_faq_crud_via_api(client, auth_headers, db_session, monkeypatch) -> None:
    async def _fake_embed(text: str):
        return [0.1] * 384

    monkeypatch.setattr(knowledge_service, "_try_embed", _fake_embed)
    response = await client.post(
        "/api/v1/datasources",
        headers=auth_headers,
        json={"name": "knowledge-faq-ds", "type": "customer_service"},
    )
    datasource_id = response.json()["id"]
    base = f"/api/v1/datasources/{datasource_id}/knowledge/faq"

    created = await client.post(
        base,
        headers=auth_headers,
        json={"question": "支持货到付款吗？", "answer": "支持", "category": "支付"},
    )
    assert created.status_code == 201, created.text
    faq_id = created.json()["id"]
    assert created.json()["source"] == "manual"

    listed = await client.get(base, headers=auth_headers)
    assert listed.status_code == 200
    assert listed.json()["pagination"]["total"] == 1

    patched = await client.patch(
        f"{base}/{faq_id}",
        headers=auth_headers,
        json={"answer": "支持，需 10 元手续费"},
    )
    assert patched.status_code == 200
    assert patched.json()["answer"] == "支持，需 10 元手续费"

    deleted = await client.delete(f"{base}/{faq_id}", headers=auth_headers)
    assert deleted.status_code == 204

    missing = await client.patch(
        f"{base}/{uuid.uuid4()}",
        headers=auth_headers,
        json={"answer": "x"},
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "FAQ_NOT_FOUND"


async def test_search_hybrid_and_trigram_fallback(
    client, auth_headers, db_session, monkeypatch
) -> None:
    response = await client.post(
        "/api/v1/datasources",
        headers=auth_headers,
        json={"name": "knowledge-search-ds", "type": "customer_service"},
    )
    datasource_id = response.json()["id"]
    await persist(
        db_session,
        KnowledgeBaseFactory(
            datasource_id=uuid.UUID(datasource_id),
            question="如何退货？",
            answer="7 天内可无理由退货",
            category="售后",
            embedding=[0.1] * 384,
        ),
    )

    async def _fake_embed(texts: list[str]):
        return [[0.1] * 384 for _ in texts]

    monkeypatch.setattr(knowledge_service.embedding_service, "encode_texts", _fake_embed)
    hybrid = await client.get(
        f"/api/v1/datasources/{datasource_id}/knowledge/search",
        headers=auth_headers,
        params={"q": "退货", "threshold": 0.3},
    )
    assert hybrid.status_code == 200, hybrid.text
    assert hybrid.json()["total"] == 1
    assert hybrid.json()["results"][0]["similarity"] > 0.3

    async def _broken(texts: list[str]):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(knowledge_service.embedding_service, "encode_texts", _broken)
    trigram = await client.get(
        f"/api/v1/datasources/{datasource_id}/knowledge/search",
        headers=auth_headers,
        params={"q": "退货", "threshold": 0.1},
    )
    assert trigram.status_code == 200
    assert trigram.json()["total"] == 1


async def test_gaps_api_after_extraction(
    client, auth_headers, db_session, test_user, monkeypatch
) -> None:
    response = await client.post(
        "/api/v1/datasources",
        headers=auth_headers,
        json={"name": "knowledge-gaps-ds", "type": "customer_service"},
    )
    datasource_id = uuid.UUID(response.json()["id"])
    completed = TaskFactory(
        user_id=test_user.id,
        datasource_id=datasource_id,
        task_type="extract",
        status="completed",
        params={},
        result={"gaps": _GAPS, "gaps_count": 2},
    )
    await persist(db_session, completed)

    gaps = await client.get(
        f"/api/v1/datasources/{datasource_id}/knowledge/gaps",
        headers=auth_headers,
    )

    assert gaps.status_code == 200, gaps.text
    body = gaps.json()
    assert body["summary"]["total_gaps"] == 2
    assert body["summary"]["high_priority"] == 1
    assert body["summary"]["low_priority"] == 1


async def test_knowledge_forbidden_for_other_user(client, auth_headers, db_session) -> None:
    from app.core.security import hash_password

    response = await client.post(
        "/api/v1/datasources",
        headers=auth_headers,
        json={"name": "knowledge-403-ds", "type": "customer_service"},
    )
    datasource_id = response.json()["id"]
    other = UserFactory(password_hash=hash_password("other12345"))
    await persist(db_session, other)
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": other.email, "password": "other12345"},
    )
    token = login.json()["access_token"]

    listed = await client.get(
        f"/api/v1/datasources/{datasource_id}/knowledge/faq",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert listed.status_code == 403
    assert listed.json()["error"]["code"] == "AUTH_FORBIDDEN"


async def test_extraction_task_registered() -> None:
    import app.tasks  # noqa: F401 - 触发任务模块注册
    from app.core.celery import celery_app

    assert "tasks.extract_knowledge" in celery_app.tasks
