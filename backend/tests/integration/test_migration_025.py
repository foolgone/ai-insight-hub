"""025 M4-A PR-3：移除业务表 tenant_id 默认值。"""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.tenancy import DEFAULT_TENANT_ID

pytestmark = pytest.mark.integration

BACKEND_DIR = Path(__file__).resolve().parents[2]
REV_024 = "c1d5f8a3e7b2"

BUSINESS_TABLES = [
    "users",
    "data_sources",
    "raw_data",
    "cleaned_data",
    "analysis_results",
    "knowledge_base",
    "knowledge_gaps",
    "tasks",
    "reports",
    "qa_datasets",
    "qa_dataset_versions",
    "qa_dataset_items",
    "rag_traces",
    "rag_evaluation_runs",
    "rag_evaluation_results",
]


def _sync_url() -> str:
    return settings.DATABASE_URL.replace("+asyncpg", "")


def _alembic_config() -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    return config


def _tenant_defaults() -> dict[str, str | None]:
    engine = create_engine(_sync_url())
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT table_name, column_default
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND column_name = 'tenant_id'
                    """
                )
            ).all()
            return {row[0]: row[1] for row in rows}
    finally:
        engine.dispose()


def test_025_business_tables_have_no_tenant_default() -> None:
    defaults = _tenant_defaults()
    for table in BUSINESS_TABLES:
        assert table in defaults
        assert defaults[table] is None, table

    # 平台级记录保持允许 NULL，且不引入默认值
    for table in ("audit_logs", "llm_calls"):
        assert defaults[table] is None


def test_025_insert_without_tenant_is_rejected() -> None:
    """025 之后，业务表不再兜底到默认租户；缺 tenant 的写入必须失败。"""
    engine = create_engine(_sync_url())
    try:
        with engine.begin() as conn:
            user_id = conn.execute(text("SELECT id FROM users LIMIT 1")).scalar_one()
            with pytest.raises(IntegrityError):
                conn.execute(
                    text(
                        """
                        INSERT INTO data_sources
                            (id, user_id, name, type, status, workflow_status)
                        VALUES
                            (:id, :user_id, 'no-tenant-default',
                             'customer_service', 'active', 'created')
                        """
                    ),
                    {"id": uuid.uuid4(), "user_id": user_id},
                )
    finally:
        engine.dispose()

    engine = create_engine(_sync_url())
    try:
        with engine.connect() as conn:
            count = conn.execute(
                text("SELECT count(*) FROM data_sources WHERE name='no-tenant-default'")
            ).scalar_one()
            assert count == 0
    finally:
        engine.dispose()


def test_025_upgrade_downgrade_twice() -> None:
    config = _alembic_config()
    for _ in range(2):
        command.downgrade(config, REV_024)
        defaults = _tenant_defaults()
        for table in BUSINESS_TABLES:
            assert defaults[table] is not None, table
            assert str(DEFAULT_TENANT_ID) in defaults[table], table

        command.upgrade(config, "head")
        defaults = _tenant_defaults()
        for table in BUSINESS_TABLES:
            assert defaults[table] is None, table
