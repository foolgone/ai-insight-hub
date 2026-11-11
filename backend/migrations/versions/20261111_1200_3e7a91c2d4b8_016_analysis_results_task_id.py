"""016 analysis_results 增加批次（task_id）

背景：评估/洞察/摘要结果都写 ``analysis_results``，但没有记录是哪个任务产生的，
导致只能按 ``created_at`` 猜「上一次评估」，无法回答「改了之后有没有变好」。

本迁移只加列和索引，**不回填历史数据**：历史结果归属不确定，宁可留空，
也不按时间就近匹配伪造批次。

Revision ID: 3e7a91c2d4b8
Revises: c7d2e9b4a165
Create Date: 2026-11-11 12:00:00+08:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "3e7a91c2d4b8"
down_revision: Union[str, None] = "c7d2e9b4a165"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "analysis_results",
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    # 不建外键：任务可能被清理，与 llm_calls.task_id 的处理保持一致
    op.create_index("idx_analysis_task_id", "analysis_results", ["task_id"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_analysis_task_id", table_name="analysis_results")
    op.drop_column("analysis_results", "task_id")
