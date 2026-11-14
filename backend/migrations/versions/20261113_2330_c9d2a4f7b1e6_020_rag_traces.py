"""020 RAG 执行链路（rag_traces）

只新增一张表：``rag_traces`` —— 一次 RAG 调用的完整快照
（问题、上下文、答案、配置、耗时、缺失字段、原始响应、状态/错误）。

``rag_eval_results`` 推迟到 Phase 3：与指标写入方一起建表，避免「只建表不实现功能」。

Revision ID: c9d2a4f7b1e6
Revises: b2f7c1d9e4a3
Create Date: 2026-11-13 23:30:00+08:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c9d2a4f7b1e6"
down_revision: Union[str, None] = "b2f7c1d9e4a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rag_traces",
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
            "dataset_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("qa_dataset_items.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("idempotency_key", sa.String(length=120), nullable=True),
        sa.Column("adapter", sa.String(length=50), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("context_source", sa.String(length=20), nullable=False, server_default="none"),
        sa.Column("external_session_id", sa.String(length=100), nullable=True),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column(
            "retrieved_contexts",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("raw_response", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "model_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "retrieval_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "prompt_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("token_usage", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "missing",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("mode IN ('retrieve', 'query')", name="rag_trace_mode_valid"),
        sa.CheckConstraint("status IN ('success', 'failed')", name="rag_trace_status_valid"),
        sa.CheckConstraint(
            "context_source IN ('hybrid_search', 'agent_chat', 'none')",
            name="rag_trace_context_source_valid",
        ),
    )
    op.create_index(
        "uk_rag_traces_idempotency_key", "rag_traces", ["idempotency_key"], unique=True
    )
    op.create_index(
        "idx_rag_traces_user_created", "rag_traces", ["user_id", "created_at"]
    )
    op.create_index("idx_rag_traces_task_status", "rag_traces", ["task_id", "status"])
    op.create_index("idx_rag_traces_dataset_item", "rag_traces", ["dataset_item_id"])


def downgrade() -> None:
    op.drop_index("idx_rag_traces_dataset_item", table_name="rag_traces")
    op.drop_index("idx_rag_traces_task_status", table_name="rag_traces")
    op.drop_index("idx_rag_traces_user_created", table_name="rag_traces")
    op.drop_index("uk_rag_traces_idempotency_key", table_name="rag_traces")
    op.drop_table("rag_traces")
