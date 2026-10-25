"""B-204 ORM 模型契约测试（与数据库设计 §3 对齐）。"""
from __future__ import annotations

import pytest

from app.models import Base, CleanedData, KnowledgeBase, LlmCall, PromptVersion, User

pytestmark = pytest.mark.unit

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


def _table(name: str):
    return Base.metadata.tables[name]


def test_all_15_tables_registered() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES
    assert len(Base.metadata.tables) == 15


@pytest.mark.parametrize(
    ("table", "columns"),
    [
        ("users", {"id", "email", "password_hash", "role", "quota", "usage", "deleted_at"}),
        ("data_sources", {"id", "user_id", "type", "status", "workflow_status", "config"}),
        ("raw_data", {"id", "datasource_id", "raw_content", "file_info", "status"}),
        ("cleaned_data", {"id", "datasource_id", "raw_data_id", "embedding", "issues"}),
        ("analysis_results", {"id", "datasource_id", "data_id", "analysis_type", "result"}),
        ("knowledge_base", {"id", "question", "answer", "source", "is_seed", "embedding"}),
        ("reports", {"id", "datasource_id", "user_id", "report_type", "format", "status"}),
        ("tasks", {"id", "task_type", "status", "progress", "celery_task_id"}),
        ("api_keys", {"id", "user_id", "key_hash", "key_prefix", "scopes"}),
        ("audit_logs", {"id", "user_id", "action", "resource_type", "ip_address"}),
        ("webhooks", {"id", "user_id", "url", "events", "secret"}),
        ("prompt_versions", {"id", "agent_name", "version", "system_prompt", "is_default"}),
        ("prompt_usage_logs", {"id", "prompt_version_id", "agent_name", "version", "cost"}),
        ("version_rollback_logs", {"id", "agent_name", "from_version", "to_version"}),
        ("llm_calls", {"id", "idempotency_key", "model", "total_cost", "status"}),
    ],
)
def test_required_columns_exist(table: str, columns: set[str]) -> None:
    assert columns <= set(_table(table).columns.keys())


def test_foreign_keys_follow_design() -> None:
    def fk_targets(name: str) -> set[tuple[str, str]]:
        table = _table(name)
        return {(fk.parent.name, fk.column.table.name) for fk in table.foreign_keys}

    assert ("user_id", "users") in fk_targets("data_sources")
    assert ("datasource_id", "data_sources") in fk_targets("cleaned_data")
    assert ("datasource_id", "data_sources") in fk_targets("analysis_results")
    assert ("datasource_id", "data_sources") in fk_targets("reports")
    assert ("prompt_version_id", "prompt_versions") in fk_targets("prompt_usage_logs")
    assert ("user_id", "users") in fk_targets("llm_calls")

    # 逻辑外键：不建 REFERENCES
    assert "raw_data_id" not in {fk.parent.name for fk in _table("cleaned_data").foreign_keys}
    assert "data_id" not in {fk.parent.name for fk in _table("analysis_results").foreign_keys}


def test_cleaned_data_fk_cascades_on_delete() -> None:
    fk = next(iter(_table("cleaned_data").foreign_keys))
    assert fk.ondelete == "CASCADE"


def test_audit_log_user_fk_sets_null() -> None:
    fk = next(iter(_table("audit_logs").foreign_keys))
    assert fk.ondelete == "SET NULL"


def test_embedding_columns_are_384_dim() -> None:
    assert CleanedData.__table__.c.embedding.type.dim == 384
    assert KnowledgeBase.__table__.c.embedding.type.dim == 384


def test_hnsw_indexes_match_design() -> None:
    for table, index_name in (
        (CleanedData, "idx_cleaned_data_embedding"),
        (KnowledgeBase, "idx_kb_embedding"),
    ):
        index = next(i for i in table.__table__.indexes if i.name == index_name)
        options = index.dialect_options["postgresql"]
        assert options["using"] == "hnsw"
        assert options["with"] == {"m": 16, "ef_construction": 64}


def test_partial_and_gin_indexes_exist() -> None:
    tables = Base.metadata.tables

    users_where = next(
        i for i in tables["users"].indexes if i.name == "idx_users_email"
    ).dialect_options["postgresql"]["where"]
    assert users_where is not None

    assert any(i.name == "idx_cleaned_data_ds_quality" for i in tables["cleaned_data"].indexes)
    assert any(
        i.dialect_options["postgresql"].get("using") == "gin"
        for i in tables["data_sources"].indexes
    )


def test_unique_constraints() -> None:
    assert User.__table__.c.email.unique is True
    assert LlmCall.__table__.c.idempotency_key is not None
    unique_indexes = {i.name for i in LlmCall.__table__.indexes if i.unique}
    assert "uk_llm_calls_idempotency" in unique_indexes

    prompt_version_uniques = {
        tuple(c.name for c in constraint.columns)
        for constraint in PromptVersion.__table__.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("agent_name", "version") in prompt_version_uniques


def test_enum_check_constraints() -> None:
    checks = {
        constraint.name
        for constraint in _table("tasks").constraints
        if constraint.__class__.__name__ == "CheckConstraint"
    }
    assert {
        "ck_tasks_status_valid",
        "ck_tasks_task_type_valid",
        "ck_tasks_progress_range",
    } <= checks
