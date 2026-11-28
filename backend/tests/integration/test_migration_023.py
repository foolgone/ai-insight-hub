"""023 M4-A tenant slice：schema、回填、up/down 与默认租户。"""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from app.core.config import settings
from app.core.tenancy import DEFAULT_TENANT_ID, DEFAULT_TENANT_SLUG

pytestmark = pytest.mark.integration

BACKEND_DIR = Path(__file__).resolve().parents[2]
REV_022 = "f3a9c2d7e1b4"

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
PLATFORM_LOG_TABLES = ["audit_logs", "llm_calls"]
EXPECTED_INDEXES = [
    "idx_users_tenant_created",
    "idx_data_sources_tenant_user",
    "idx_tasks_tenant_status",
    "idx_reports_tenant_datasource_created",
    "idx_qa_dataset_items_tenant_version",
    "idx_rag_evaluation_results_tenant_run",
    "idx_audit_logs_tenant_created",
    "idx_llm_calls_tenant_user_created",
]


def _sync_url() -> str:
    return settings.DATABASE_URL.replace("+asyncpg", "")


def _alembic_config() -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    return config


def _fetch(sql: str, **params: object) -> list[tuple[object, ...]]:
    engine = create_engine(_sync_url())
    try:
        with engine.connect() as conn:
            return list(conn.execute(text(sql), params).all())
    finally:
        engine.dispose()


def _scalar(sql: str, **params: object):
    engine = create_engine(_sync_url())
    try:
        with engine.connect() as conn:
            return conn.execute(text(sql), params).scalar()
    finally:
        engine.dispose()


def _execute(sql: str, **params: object) -> None:
    engine = create_engine(_sync_url())
    try:
        with engine.begin() as conn:
            conn.execute(text(sql), params)
    finally:
        engine.dispose()


def test_023_schema_default_tenant_and_indexes() -> None:
    tenant = _fetch(
        "SELECT id, name, slug, status FROM tenants WHERE slug = :slug", slug=DEFAULT_TENANT_SLUG
    )
    assert len(tenant) == 1
    assert str(tenant[0][0]) == str(DEFAULT_TENANT_ID)
    assert tenant[0][3] == "active"

    for table in BUSINESS_TABLES:
        nullable = _scalar(
            """
            SELECT is_nullable FROM information_schema.columns
            WHERE table_name = :table AND column_name = 'tenant_id'
            """,
            table=table,
        )
        assert nullable == "NO", table
    for table in PLATFORM_LOG_TABLES:
        nullable = _scalar(
            """
            SELECT is_nullable FROM information_schema.columns
            WHERE table_name = :table AND column_name = 'tenant_id'
            """,
            table=table,
        )
        assert nullable == "YES", table

    for index in EXPECTED_INDEXES:
        found = _scalar(
            "SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = :name",
            name=index,
        )
        assert found == 1, index


def _insert_legacy_rows(conn: Connection) -> dict[str, uuid.UUID]:
    ids = {
        key: uuid.uuid4()
        for key in ("user", "datasource", "raw", "cleaned", "dataset", "version", "item", "run")
    }

    conn.execute(
        text(
            "INSERT INTO users (id, email, password_hash, role) VALUES (:id, :email, 'x', 'user')"
        ),
        {"id": ids["user"], "email": f"migration023-{uuid.uuid4().hex[:8]}@example.com"},
    )
    conn.execute(
        text(
            "INSERT INTO data_sources (id, user_id, name, type) "
            "VALUES (:id, :user_id, 'migration023-ds', 'customer_service')"
        ),
        {"id": ids["datasource"], "user_id": ids["user"]},
    )
    conn.execute(
        text(
            "INSERT INTO raw_data (id, datasource_id, raw_content) "
            "VALUES (:id, :datasource_id, '{}'::jsonb)"
        ),
        {"id": ids["raw"], "datasource_id": ids["datasource"]},
    )
    conn.execute(
        text(
            "INSERT INTO cleaned_data "
            "(id, datasource_id, raw_data_id, dialogue_id, user_message, ai_response) "
            "VALUES (:id, :datasource_id, :raw_id, :dialogue_id, 'hello', 'hi')"
        ),
        {
            "id": ids["cleaned"],
            "datasource_id": ids["datasource"],
            "raw_id": ids["raw"],
            "dialogue_id": uuid.uuid4(),
        },
    )
    conn.execute(
        text(
            "INSERT INTO analysis_results "
            "(id, datasource_id, analysis_type, result, agent_name) "
            "VALUES (:id, :datasource_id, 'quality', '{}'::jsonb, 'quality_agent')"
        ),
        {"id": uuid.uuid4(), "datasource_id": ids["datasource"]},
    )
    conn.execute(
        text(
            "INSERT INTO knowledge_base (id, datasource_id, question, answer) "
            "VALUES (:id, :datasource_id, 'q?', 'a')"
        ),
        {"id": uuid.uuid4(), "datasource_id": ids["datasource"]},
    )
    conn.execute(
        text(
            "INSERT INTO knowledge_gaps (id, datasource_id, question, question_key) "
            "VALUES (:id, :datasource_id, 'gap?', 'gap-key')"
        ),
        {"id": uuid.uuid4(), "datasource_id": ids["datasource"]},
    )
    conn.execute(
        text(
            "INSERT INTO tasks (id, task_type, user_id, datasource_id) "
            "VALUES (:id, 'clean', :user_id, :datasource_id)"
        ),
        {"id": uuid.uuid4(), "user_id": ids["user"], "datasource_id": ids["datasource"]},
    )
    conn.execute(
        text(
            "INSERT INTO reports (id, datasource_id, user_id, title, report_type, format) "
            "VALUES (:id, :datasource_id, :user_id, 'legacy report', 'quality', 'markdown')"
        ),
        {"id": uuid.uuid4(), "datasource_id": ids["datasource"], "user_id": ids["user"]},
    )
    conn.execute(
        text("INSERT INTO qa_datasets (id, user_id, name) " "VALUES (:id, :user_id, 'legacy-ds')"),
        {"id": ids["dataset"], "user_id": ids["user"]},
    )
    conn.execute(
        text(
            "INSERT INTO qa_dataset_versions (id, dataset_id, version) "
            "VALUES (:id, :dataset_id, 1)"
        ),
        {"id": ids["version"], "dataset_id": ids["dataset"]},
    )
    conn.execute(
        text(
            "INSERT INTO qa_dataset_items (id, version_id, item_key, query) "
            "VALUES (:id, :version_id, 'Q1', 'q')"
        ),
        {"id": ids["item"], "version_id": ids["version"]},
    )
    conn.execute(
        text(
            "INSERT INTO rag_traces "
            "(id, user_id, dataset_item_id, adapter, mode, query, status) "
            "VALUES (:id, :user_id, :item_id, 'mock', 'query', 'q', 'success')"
        ),
        {"id": uuid.uuid4(), "user_id": ids["user"], "item_id": ids["item"]},
    )
    conn.execute(
        text(
            "INSERT INTO rag_evaluation_runs "
            "(id, user_id, dataset_id, dataset_name, dataset_version_id, execution_mode, adapter) "
            "VALUES (:id, :user_id, :dataset_id, 'legacy-ds', :version_id, 'query', 'mock')"
        ),
        {
            "id": ids["run"],
            "user_id": ids["user"],
            "dataset_id": ids["dataset"],
            "version_id": ids["version"],
        },
    )
    conn.execute(
        text(
            "INSERT INTO rag_evaluation_results "
            "(id, run_id, dataset_item_id, metric_name, metric_version, status) "
            "VALUES (:id, :run_id, :item_id, 'faithfulness', 'v3', 'evaluated')"
        ),
        {"id": uuid.uuid4(), "run_id": ids["run"], "item_id": ids["item"]},
    )
    conn.execute(
        text(
            "INSERT INTO audit_logs (user_id, action, resource_type) "
            "VALUES (NULL, 'legacy.action', 'legacy')"
        )
    )
    conn.execute(
        text(
            "INSERT INTO llm_calls "
            "(id, idempotency_key, service, model, input_tokens, output_tokens, "
            "total_tokens, input_cost, output_cost, total_cost) "
            "VALUES (:id, :key, 'deepseek', 'deepseek-flash', 1, 1, 2, 0, 0, 0)"
        ),
        {"id": uuid.uuid4(), "key": f"legacy-{uuid.uuid4().hex[:8]}"},
    )
    return ids


def _cleanup_legacy_rows(ids: dict[str, uuid.UUID]) -> None:
    engine = create_engine(_sync_url())
    try:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM rag_evaluation_results WHERE run_id = :id"), {"id": ids["run"]}
            )
            conn.execute(text("DELETE FROM rag_evaluation_runs WHERE id = :id"), {"id": ids["run"]})
            conn.execute(text("DELETE FROM rag_traces WHERE user_id = :id"), {"id": ids["user"]})
            conn.execute(text("DELETE FROM qa_dataset_items WHERE id = :id"), {"id": ids["item"]})
            conn.execute(
                text("DELETE FROM qa_dataset_versions WHERE id = :id"), {"id": ids["version"]}
            )
            conn.execute(text("DELETE FROM qa_datasets WHERE id = :id"), {"id": ids["dataset"]})
            conn.execute(text("DELETE FROM reports WHERE user_id = :id"), {"id": ids["user"]})
            conn.execute(text("DELETE FROM tasks WHERE user_id = :id"), {"id": ids["user"]})
            conn.execute(
                text("DELETE FROM knowledge_gaps WHERE datasource_id = :id"),
                {"id": ids["datasource"]},
            )
            conn.execute(
                text("DELETE FROM knowledge_base WHERE datasource_id = :id"),
                {"id": ids["datasource"]},
            )
            conn.execute(
                text("DELETE FROM analysis_results WHERE datasource_id = :id"),
                {"id": ids["datasource"]},
            )
            conn.execute(
                text("DELETE FROM cleaned_data WHERE datasource_id = :id"),
                {"id": ids["datasource"]},
            )
            conn.execute(
                text("DELETE FROM raw_data WHERE datasource_id = :id"),
                {"id": ids["datasource"]},
            )
            conn.execute(text("DELETE FROM data_sources WHERE id = :id"), {"id": ids["datasource"]})
            conn.execute(text("DELETE FROM users WHERE id = :id"), {"id": ids["user"]})
            conn.execute(text("DELETE FROM audit_logs WHERE action = 'legacy.action'"))
            conn.execute(text("DELETE FROM llm_calls WHERE idempotency_key LIKE 'legacy-%'"))
    finally:
        engine.dispose()


def test_023_backfill_legacy_rows_to_default_tenant() -> None:
    config = _alembic_config()
    command.downgrade(config, REV_022)
    ids = {}
    try:
        engine = create_engine(_sync_url())
        try:
            with engine.begin() as conn:
                ids = _insert_legacy_rows(conn)
        finally:
            engine.dispose()

        command.upgrade(config, "head")

        for table in BUSINESS_TABLES:
            bad = _scalar(
                f"SELECT count(*) FROM {table} WHERE tenant_id IS DISTINCT FROM :tenant",
                tenant=DEFAULT_TENANT_ID,
            )
            assert bad == 0, table
        # audit_logs / llm_calls 的存量 NULL 用户记录回填到默认租户
        assert (
            _scalar(
                "SELECT count(*) FROM audit_logs WHERE action='legacy.action' "
                "AND tenant_id IS DISTINCT FROM :tenant",
                tenant=DEFAULT_TENANT_ID,
            )
            == 0
        )
        assert (
            _scalar(
                "SELECT count(*) FROM llm_calls WHERE idempotency_key LIKE 'legacy-%' "
                "AND tenant_id IS DISTINCT FROM :tenant",
                tenant=DEFAULT_TENANT_ID,
            )
            == 0
        )
        # 父子一致
        assert (
            _scalar(
                """
                SELECT count(*) FROM rag_evaluation_results AS r
                JOIN rag_evaluation_runs AS run ON run.id = r.run_id
                WHERE r.tenant_id IS DISTINCT FROM run.tenant_id
                """
            )
            == 0
        )
    finally:
        if ids:
            _cleanup_legacy_rows(ids)
        command.upgrade(config, "head")


def test_023_upgrade_downgrade_twice() -> None:
    config = _alembic_config()
    for _ in range(2):
        command.downgrade(config, REV_022)
        assert (
            _scalar(
                "SELECT count(*) FROM information_schema.columns "
                "WHERE table_name='users' AND column_name='tenant_id'"
            )
            == 0
        )
        command.upgrade(config, "head")
        assert (
            _scalar(
                "SELECT count(*) FROM tenants WHERE id = :id AND slug = :slug",
                id=DEFAULT_TENANT_ID,
                slug=DEFAULT_TENANT_SLUG,
            )
            == 1
        )


async def test_user_default_tenant_for_legacy_login(test_user) -> None:
    """PR-1 不接 JWT；已有/新用户均落默认租户，后续 PR-2 再进 token。"""
    assert test_user.tenant_id == DEFAULT_TENANT_ID
