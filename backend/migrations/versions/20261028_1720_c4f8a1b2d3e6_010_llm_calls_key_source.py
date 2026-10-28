"""010 llm_calls key_source

BYOK 成本隔离：``llm_calls.key_source``（'server' / 'user'）。
降级统计只聚合 ``server``，用户自付成本不触发平台降级（需求 §5 / AC-BK-15）。

Revision ID: c4f8a1b2d3e6
Revises: b7c41e9d2f30
Create Date: 2026-10-28 17:20:00+08:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4f8a1b2d3e6"
down_revision: Union[str, None] = "b7c41e9d2f30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "llm_calls",
        sa.Column("key_source", sa.String(length=10), server_default="server", nullable=False),
    )
    op.create_index(
        "idx_llm_calls_key_source_date", "llm_calls", ["key_source", "created_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("idx_llm_calls_key_source_date", table_name="llm_calls")
    op.drop_column("llm_calls", "key_source")
