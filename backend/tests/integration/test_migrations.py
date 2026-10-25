"""B-205 迁移集成测试：验证数据库结构与设计一致。

前置：``alembic upgrade head`` 已执行（或 CI 中由 workflow 先执行迁移）。
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.core.database import engine

pytestmark = pytest.mark.integration

EXPECTED_TABLES = {
    "users",
    "data_sources",
    "raw_data",
    "cleaned_data",
    "analysis_results",
    "knowledge_base",
    "reports",
    "tasks",
    "api_keys",
    "audit_logs",
    "webhooks",
    "prompt_versions",
    "prompt_usage_logs",
    "version_rollback_logs",
    "llm_calls",
}


async def _fetch_scalars(sql: str, **params: object) -> list[str]:
    async with engine.connect() as conn:
        result = await conn.execute(text(sql), params)
        return [str(row[0]) for row in result.all()]


async def test_all_business_tables_created() -> None:
    tables = set(
        await _fetch_scalars(
            """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            """
        )
    )
    assert EXPECTED_TABLES <= tables


async def test_required_extensions_installed() -> None:
    extensions = set(await _fetch_scalars("SELECT extname FROM pg_extension"))
    assert {"vector", "pg_trgm", "pgcrypto"} <= extensions


async def test_hnsw_vector_indexes_created() -> None:
    indexes = await _fetch_scalars("SELECT indexdef FROM pg_indexes WHERE schemaname = 'public'")
    hnsw = [item for item in indexes if "hnsw" in item.lower()]
    assert any("idx_cleaned_data_embedding" in item for item in hnsw)
    assert any("idx_kb_embedding" in item for item in hnsw)
    for item in hnsw:
        assert "vector_cosine_ops" in item


async def test_trigram_indexes_created() -> None:
    indexes = await _fetch_scalars("SELECT indexdef FROM pg_indexes WHERE schemaname = 'public'")
    assert any("idx_cleaned_data_search" in item for item in indexes)
    assert any("idx_kb_search" in item for item in indexes)


async def test_partial_and_unique_indexes_created() -> None:
    indexes = await _fetch_scalars("SELECT indexdef FROM pg_indexes WHERE schemaname = 'public'")
    cleaned = [item for item in indexes if "idx_cleaned_data_ds_quality" in item]
    assert cleaned and "quality_score <" in cleaned[0] and "70" in cleaned[0]

    users_email = [item for item in indexes if "idx_users_email" in item]
    assert users_email and "deleted_at IS NULL" in users_email[0]

    idempotency = [item for item in indexes if "uk_llm_calls_idempotency" in item]
    assert idempotency and "UNIQUE" in idempotency[0]


async def test_alembic_version_at_head() -> None:
    versions = await _fetch_scalars("SELECT version_num FROM alembic_version")
    assert len(versions) == 1
    assert versions[0]
