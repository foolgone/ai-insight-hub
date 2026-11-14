"""021 RAG 评测持久化与批量执行

新增：
- ``rag_evaluation_runs``：一次固定配置的评测执行（含配置快照、计数、心跳、聚合）；
- ``rag_evaluation_results``：Run × 样本 × 指标 的结果（唯一键保证幂等）。

同时调整 ``tasks.task_type`` CHECK，加入 ``rag_eval``（不改 status 枚举）。

Revision ID: d4e8b1c6f902
Revises: c9d2a4f7b1e6
Create Date: 2026-11-14 18:00:00+08:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d4e8b1c6f902"
down_revision: Union[str, None] = "c9d2a4f7b1e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD_TASK_TYPES = (
    "clean",
    "structure",
    "evaluate",
    "extract",
    "analyze",
    "report",
)
_NEW_TASK_TYPES = (*_OLD_TASK_TYPES, "rag_eval")


def _task_type_check(types: Sequence[str]) -> str:
    values = ", ".join(f"'{item}'" for item in types)
    return f"task_type IN ({values})"


def upgrade() -> None:
    # 1) 允许 rag_eval 任务类型（表小，维护窗口执行）
    op.drop_constraint("task_type_valid", "tasks", type_="check")
    op.create_check_constraint(
        "task_type_valid", "tasks", _task_type_check(_NEW_TASK_TYPES)
    )

    # 2) 评测 Run
    op.create_table(
        "rag_evaluation_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "parent_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("rag_evaluation_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("retry_scope", sa.String(length=20), nullable=False, server_default="all"),
        sa.Column(
            "dataset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("qa_datasets.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("dataset_name", sa.String(length=200), nullable=False),
        sa.Column(
            "dataset_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("qa_dataset_versions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("dataset_checksum", sa.String(length=64), nullable=True),
        sa.Column("execution_mode", sa.String(length=20), nullable=False),
        sa.Column("adapter", sa.String(length=50), nullable=False),
        sa.Column(
            "retrieval_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "judge_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "config_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "item_selection",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("total_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("aggregate", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "retry_scope IN ('all', 'failed_only')", name="rag_eval_run_retry_scope_valid"
        ),
        sa.CheckConstraint(
            "execution_mode IN ('retrieve', 'query')", name="rag_eval_run_mode_valid"
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'partial_failed', 'failed', 'cancelled')",
            name="rag_eval_run_status_valid",
        ),
    )
    op.create_index(
        "uk_rag_evaluation_runs_task_id", "rag_evaluation_runs", ["task_id"], unique=True
    )
    op.create_index(
        "idx_rag_evaluation_runs_user_created",
        "rag_evaluation_runs",
        ["user_id", "created_at"],
    )
    op.create_index(
        "idx_rag_evaluation_runs_dataset_version",
        "rag_evaluation_runs",
        ["dataset_version_id"],
    )
    op.create_index("idx_rag_evaluation_runs_status", "rag_evaluation_runs", ["status"])
    op.create_index(
        "idx_rag_evaluation_runs_parent", "rag_evaluation_runs", ["parent_run_id"]
    )

    # 3) 评测结果
    op.create_table(
        "rag_evaluation_results",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("rag_evaluation_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "dataset_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("qa_dataset_items.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "trace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("rag_traces.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("metric_name", sa.String(length=40), nullable=False),
        sa.Column("metric_version", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("skipped_reason", sa.String(length=60), nullable=True),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "judge_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("raw_output", sa.Text(), nullable=True),
        sa.Column(
            "raw_truncated", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "status IN ('evaluated', 'skipped', 'failed')",
            name="rag_eval_result_status_valid",
        ),
    )
    op.create_index(
        "uk_rag_evaluation_results_run_item_metric",
        "rag_evaluation_results",
        ["run_id", "dataset_item_id", "metric_name", "metric_version"],
        unique=True,
    )
    op.create_index(
        "idx_rag_evaluation_results_run_metric",
        "rag_evaluation_results",
        ["run_id", "metric_name", "status"],
    )
    op.create_index(
        "idx_rag_evaluation_results_run_status", "rag_evaluation_results", ["run_id", "status"]
    )
    op.create_index(
        "idx_rag_evaluation_results_trace", "rag_evaluation_results", ["trace_id"]
    )


def downgrade() -> None:
    op.drop_index("idx_rag_evaluation_results_trace", table_name="rag_evaluation_results")
    op.drop_index(
        "idx_rag_evaluation_results_run_status", table_name="rag_evaluation_results"
    )
    op.drop_index(
        "idx_rag_evaluation_results_run_metric", table_name="rag_evaluation_results"
    )
    op.drop_index(
        "uk_rag_evaluation_results_run_item_metric", table_name="rag_evaluation_results"
    )
    op.drop_table("rag_evaluation_results")

    op.drop_index("idx_rag_evaluation_runs_parent", table_name="rag_evaluation_runs")
    op.drop_index("idx_rag_evaluation_runs_status", table_name="rag_evaluation_runs")
    op.drop_index(
        "idx_rag_evaluation_runs_dataset_version", table_name="rag_evaluation_runs"
    )
    op.drop_index(
        "idx_rag_evaluation_runs_user_created", table_name="rag_evaluation_runs"
    )
    op.drop_index("uk_rag_evaluation_runs_task_id", table_name="rag_evaluation_runs")
    op.drop_table("rag_evaluation_runs")

    # 回滚会丢弃 rag_eval 任务记录（Run/Result 已在上方删除）
    op.execute("DELETE FROM tasks WHERE task_type = 'rag_eval'")
    op.drop_constraint("task_type_valid", "tasks", type_="check")
    op.create_check_constraint("task_type_valid", "tasks", _task_type_check(_OLD_TASK_TYPES))
