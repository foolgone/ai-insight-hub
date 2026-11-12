"""018 知识闭环：按文件归属 + 盲区台账

1. ``knowledge_base.raw_data_id`` / ``analysis_results.raw_data_id``：
   结构化产出的知识点与摘要按文件归属，重切时整体替换（此前只能追加，重复累积）。
2. 新建 ``knowledge_gaps``：盲区从 ``tasks.result`` 快照升级为台账
   （累计 hit_count、first_seen/last_seen、open/adopted/ignored 流转）。

Revision ID: 9a4d2f8c6e15
Revises: 7c1b5a9e2f43
Create Date: 2026-11-12 19:00:00+08:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "9a4d2f8c6e15"
down_revision: Union[str, None] = "7c1b5a9e2f43"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) 按文件归属
    op.add_column(
        "knowledge_base",
        sa.Column("raw_data_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("idx_kb_raw_data_id", "knowledge_base", ["raw_data_id"])

    op.add_column(
        "analysis_results",
        sa.Column("raw_data_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("idx_analysis_raw_data_id", "analysis_results", ["raw_data_id"])

    # 2) 盲区台账
    op.create_table(
        "knowledge_gaps",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "datasource_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("data_sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("question_key", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'open'")),
        sa.Column("faq_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("hit_count", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("priority", sa.String(length=20), nullable=True),
        sa.Column("source_task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("first_seen", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("last_seen", sa.DateTime(), server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('open', 'adopted', 'ignored')", name="gap_status_valid"
        ),
    )
    op.create_index(
        "uk_kb_gaps_datasource_key",
        "knowledge_gaps",
        ["datasource_id", "question_key"],
        unique=True,
    )
    op.create_index(
        "idx_kb_gaps_status",
        "knowledge_gaps",
        ["datasource_id", "status", sa.text("last_seen DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_kb_gaps_status", table_name="knowledge_gaps")
    op.drop_index("uk_kb_gaps_datasource_key", table_name="knowledge_gaps")
    op.drop_table("knowledge_gaps")
    op.drop_index("idx_analysis_raw_data_id", table_name="analysis_results")
    op.drop_column("analysis_results", "raw_data_id")
    op.drop_index("idx_kb_raw_data_id", table_name="knowledge_base")
    op.drop_column("knowledge_base", "raw_data_id")
