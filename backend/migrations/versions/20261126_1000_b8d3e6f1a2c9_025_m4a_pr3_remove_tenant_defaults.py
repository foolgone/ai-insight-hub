"""025 M4-A PR-3：移除业务表 tenant_id 默认租户

变更：
- 15 张业务表的 ``tenant_id`` 取消 ``server_default``；
- 保留 NOT NULL 与外键约束：所有写入必须显式带 tenant；
- ``audit_logs`` / ``llm_calls`` 保持原状（平台级，允许 NULL）。

downgrade 恢复默认租户 ``server_default``，仅用于回滚；
新代码不得依赖该默认值。

Revision ID: b8d3e6f1a2c9
Revises: c1d5f8a3e7b2
Create Date: 2026-11-26 10:00:00+08:00
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b8d3e6f1a2c9"
down_revision: Union[str, None] = "c1d5f8a3e7b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"
DEFAULT_TENANT_SQL = f"'{DEFAULT_TENANT_ID}'::uuid"

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


def _alter_tenant_default(server_default: sa.text | None) -> None:
    for table in BUSINESS_TABLES:
        op.alter_column(
            table,
            "tenant_id",
            existing_type=postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=server_default,
        )


def upgrade() -> None:
    _alter_tenant_default(None)


def downgrade() -> None:
    _alter_tenant_default(sa.text(DEFAULT_TENANT_SQL))
