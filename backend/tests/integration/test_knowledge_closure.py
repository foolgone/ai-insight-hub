"""知识闭环：盲区台账（累积/流转）与知识覆盖率。"""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import knowledge_gaps as gap_repo
from tests.factories import (
    CleanedDataFactory,
    DataSourceFactory,
    KnowledgeBaseFactory,
    RawDataFactory,
    persist,
)

pytestmark = pytest.mark.integration

_VEC = [0.1] * 384
# 与 _VEC 正交（点积为 0）→ 余弦相似度 0，不会被判为命中
_OTHER = [0.1] * 192 + [-0.1] * 192


async def _datasource(session: AsyncSession, user) -> object:
    datasource = DataSourceFactory(user_id=user.id)
    await persist(session, datasource)
    return datasource


async def test_gaps_accumulate_and_status_flow(
    client: AsyncClient, db_session: AsyncSession, auth_headers: dict, test_user
) -> None:
    datasource = await _datasource(db_session, test_user)

    await gap_repo.upsert_many(
        db_session,
        datasource_id=datasource.id,
        gaps=[{"question": "能退货吗", "frequency": 2, "priority": "high"}],
    )
    # 归一化后是同一条（空格差异）→ hit_count 累加，不新增
    await gap_repo.upsert_many(
        db_session,
        datasource_id=datasource.id,
        gaps=[{"question": "能 退货 吗", "frequency": 3}],
    )

    response = await client.get(
        f"/api/v1/datasources/{datasource.id}/knowledge/gaps", headers=auth_headers
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["summary"]["total_gaps"] == 1
    assert body["summary"]["open_gaps"] == 1
    gap = body["gaps"][0]
    assert gap["frequency"] == 5
    assert gap["status"] == "open"
    assert gap["priority"] == "high"

    # 状态流转：忽略
    patched = await client.patch(
        f"/api/v1/datasources/{datasource.id}/knowledge/gaps/{gap['id']}",
        headers=auth_headers,
        json={"status": "ignored"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["status"] == "ignored"

    # 再次提取不应把已忽略状态改回 open，只累加次数
    await gap_repo.upsert_many(
        db_session,
        datasource_id=datasource.id,
        gaps=[{"question": "能退货吗", "frequency": 1}],
    )
    ignored = await client.get(
        f"/api/v1/datasources/{datasource.id}/knowledge/gaps",
        headers=auth_headers,
        params={"status": "ignored"},
    )
    assert ignored.json()["summary"]["total_gaps"] == 1
    item = ignored.json()["gaps"][0]
    assert item["status"] == "ignored"
    assert item["frequency"] == 6

    opened = await client.get(
        f"/api/v1/datasources/{datasource.id}/knowledge/gaps",
        headers=auth_headers,
        params={"status": "open"},
    )
    assert opened.json()["gaps"] == []


async def test_gap_update_rejects_other_datasource(
    client: AsyncClient, db_session: AsyncSession, auth_headers: dict, test_user
) -> None:
    first = await _datasource(db_session, test_user)
    second = await _datasource(db_session, test_user)
    await gap_repo.upsert_many(
        db_session, datasource_id=first.id, gaps=[{"question": "问题 A", "frequency": 1}]
    )
    gap = (await gap_repo.list_for_datasource(db_session, first.id))[0]

    response = await client.patch(
        f"/api/v1/datasources/{second.id}/knowledge/gaps/{gap.id}",
        headers=auth_headers,
        json={"status": "adopted"},
    )

    assert response.status_code == 404


async def test_coverage_counts_semantic_matches(
    client: AsyncClient, db_session: AsyncSession, auth_headers: dict, test_user
) -> None:
    datasource = await _datasource(db_session, test_user)
    raw = RawDataFactory(datasource_id=datasource.id)
    await persist(db_session, raw)
    await persist(
        db_session,
        KnowledgeBaseFactory(datasource_id=datasource.id, embedding=_VEC),
    )
    # 一条与 FAQ 同向量（命中），一条不同（未命中）
    await persist(
        db_session,
        CleanedDataFactory(datasource_id=datasource.id, raw_data_id=raw.id, embedding=_VEC),
    )
    await persist(
        db_session,
        CleanedDataFactory(datasource_id=datasource.id, raw_data_id=raw.id, embedding=_OTHER),
    )

    response = await client.get(
        f"/api/v1/datasources/{datasource.id}/knowledge/coverage",
        headers=auth_headers,
        params={"days": 7, "threshold": 0.8},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 2
    assert body["covered"] == 1
    assert body["rate"] == 0.5
    assert body["method"] == "vector"


async def test_coverage_falls_back_to_text_similarity_without_embeddings(
    client: AsyncClient, db_session: AsyncSession, auth_headers: dict, test_user
) -> None:
    """历史数据没有向量时用文本相似度估算，并标注 method=trgm（不再返回 0%）。"""
    datasource = await _datasource(db_session, test_user)
    raw = RawDataFactory(datasource_id=datasource.id)
    await persist(db_session, raw)
    await persist(
        db_session,
        KnowledgeBaseFactory(datasource_id=datasource.id, question="如何申请退款？"),
    )
    await persist(
        db_session,
        CleanedDataFactory(datasource_id=datasource.id, raw_data_id=raw.id, user_message="如何申请退款？"),
    )
    await persist(
        db_session,
        CleanedDataFactory(
            datasource_id=datasource.id,
            raw_data_id=raw.id,
            user_message="你们公司在哪个城市",
        ),
    )

    response = await client.get(
        f"/api/v1/datasources/{datasource.id}/knowledge/coverage",
        headers=auth_headers,
        params={"days": 7, "threshold": 0.5},
    )

    body = response.json()
    assert body["method"] == "trgm"
    assert body["total"] == 2
    assert body["covered"] == 1
    assert body["rate"] == 0.5


async def test_coverage_without_rows_is_zero(
    client: AsyncClient, db_session: AsyncSession, auth_headers: dict, test_user
) -> None:
    datasource = await _datasource(db_session, test_user)

    response = await client.get(
        f"/api/v1/datasources/{datasource.id}/knowledge/coverage", headers=auth_headers
    )

    body = response.json()
    assert body["total"] == 0
    assert body["rate"] == 0.0


async def test_coverage_without_faq_is_zero(
    client: AsyncClient, db_session: AsyncSession, auth_headers: dict, test_user
) -> None:
    datasource = await _datasource(db_session, test_user)
    raw = RawDataFactory(datasource_id=datasource.id)
    await persist(db_session, raw)
    await persist(
        db_session,
        CleanedDataFactory(datasource_id=datasource.id, raw_data_id=raw.id, embedding=_VEC),
    )

    response = await client.get(
        f"/api/v1/datasources/{datasource.id}/knowledge/coverage", headers=auth_headers
    )

    body = response.json()
    # 有向量但没有 FAQ → 向量路径 total>0、covered=0
    assert body["total"] == 1
    assert body["covered"] == 0
    assert body["rate"] == 0.0
    assert body["method"] == "vector"


async def test_coverage_ignores_rows_without_embedding(
    client: AsyncClient, db_session: AsyncSession, auth_headers: dict, test_user
) -> None:
    datasource = await _datasource(db_session, test_user)
    raw = RawDataFactory(datasource_id=datasource.id)
    await persist(db_session, raw)
    await persist(db_session, CleanedDataFactory(datasource_id=datasource.id, raw_data_id=raw.id))

    response = await client.get(
        f"/api/v1/datasources/{datasource.id}/knowledge/coverage", headers=auth_headers
    )

    body = response.json()
    # 无向量时走 trgm 降级：没有 FAQ，所以命中不进来，但总数仍按窗口统计
    assert body["method"] == "trgm"
    assert body["total"] == 1
    assert body["covered"] == 0
    assert body["rate"] == 0.0
