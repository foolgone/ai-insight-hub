"""014 数据源类型字典表

把「数据源类型」从写死的 CHECK 约束改成可增删改查的字典表：

- 新建 ``datasource_types``（code / label / sort_order / is_system / is_active）；
- 播种 4 个内置类型（客服对话 / 销售 / 支持 / 其他），与旧约束取值一致；
- 删除 ``data_sources.type`` 上的 ``ck_data_sources_type_valid``，
  取值改由 API 层校验 ``datasource_types``（``data_sources.type`` 仍存 code）。

Revision ID: f1a4c8e27b93
Revises: a3f7c2d91b84
Create Date: 2026-11-08 20:00:00+08:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f1a4c8e27b93"
down_revision: Union[str, None] = "a3f7c2d91b84"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SEED = (
    ("customer_service", "客服对话", 10),
    ("sales", "销售", 20),
    ("support", "支持", 30),
    ("other", "其他", 90),
)


def upgrade() -> None:
    op.create_table(
        "datasource_types",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("label", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_system", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "code ~ '^[a-z][a-z0-9_]{1,49}$'", name="ck_datasource_types_code_format"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_datasource_types"),
    )
    op.create_index(
        "uk_datasource_types_code", "datasource_types", ["code"], unique=True
    )
    op.create_index(
        "idx_datasource_types_sort", "datasource_types", ["sort_order"], unique=False
    )

    # 内置类型：与旧 CHECK 约束的四个取值完全一致，保证历史数据可直接对上
    for code, label, sort_order in _SEED:
        op.execute(
            sa.text(
                "INSERT INTO datasource_types (code, label, sort_order, is_system, is_active) "
                "VALUES (:code, :label, :sort_order, true, true) "
                "ON CONFLICT (code) DO NOTHING"
            ).bindparams(code=code, label=label, sort_order=sort_order)
        )

    # 类型取值改由字典表 + API 校验
    op.execute("ALTER TABLE data_sources DROP CONSTRAINT IF EXISTS ck_data_sources_type_valid")


def downgrade() -> None:
    # 回退前把自定义类型归一到「其他」，否则旧 CHECK 约束加不上
    op.execute(
        "UPDATE data_sources SET type = 'other' "
        "WHERE type NOT IN ('customer_service', 'sales', 'support', 'other')"
    )
    op.execute(
        "ALTER TABLE data_sources ADD CONSTRAINT ck_data_sources_type_valid "
        "CHECK (type IN ('customer_service', 'sales', 'support', 'other'))"
    )
    op.drop_index("idx_datasource_types_sort", table_name="datasource_types")
    op.drop_index("uk_datasource_types_code", table_name="datasource_types")
    op.drop_table("datasource_types")
