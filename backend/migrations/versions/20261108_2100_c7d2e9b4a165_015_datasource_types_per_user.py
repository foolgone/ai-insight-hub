"""015 数据源类型按用户隔离（多租户）

把全局字典改成「每个用户一套」：

1. ``datasource_types`` 增加 ``owner_user_id``（FK users，ON DELETE CASCADE）；
2. 为已存在的每个用户复制一份当前的全局类型（code/label 完全一致，
   因此历史 ``data_sources.type`` 无需回填即可对上）；
3. 删除全局模板行，收紧 ``owner_user_id NOT NULL``；
4. 唯一键 ``(code)`` → ``(owner_user_id, code)``，并补 ``(owner, sort_order)`` 索引。

Revision ID: c7d2e9b4a165
Revises: f1a4c8e27b93
Create Date: 2026-11-08 21:00:00+08:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c7d2e9b4a165"
down_revision: Union[str, None] = "f1a4c8e27b93"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "datasource_types",
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_datasource_types_owner_user_id_users",
        "datasource_types",
        "users",
        ["owner_user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # 唯一键必须先改成 (owner, code)：否则 backfill 时同一 code 会撞上旧的全局唯一索引
    op.execute("DROP INDEX IF EXISTS uk_datasource_types_code")

    # 给已存在的每个用户复制当前全局类型（此时 owner 仍为 NULL 的行就是模板）
    op.execute(
        "INSERT INTO datasource_types "
        "(owner_user_id, code, label, description, sort_order, is_system, is_active) "
        "SELECT u.id, t.code, t.label, t.description, t.sort_order, true, t.is_active "
        "FROM users u CROSS JOIN datasource_types t "
        "WHERE t.owner_user_id IS NULL"
    )

    op.execute("DELETE FROM datasource_types WHERE owner_user_id IS NULL")
    op.alter_column("datasource_types", "owner_user_id", nullable=False)

    op.execute("DROP INDEX IF EXISTS idx_datasource_types_sort")
    op.create_index(
        "uk_datasource_types_owner_code",
        "datasource_types",
        ["owner_user_id", "code"],
        unique=True,
    )
    op.create_index(
        "idx_datasource_types_owner_sort",
        "datasource_types",
        ["owner_user_id", "sort_order"],
        unique=False,
    )


def downgrade() -> None:
    # 回退：只保留一份全局模板（按 code 去重），再恢复原唯一键
    op.execute("DELETE FROM datasource_types WHERE is_system IS NOT TRUE")
    op.execute(
        "DELETE FROM datasource_types a USING datasource_types b "
        "WHERE a.code = b.code AND a.ctid > b.ctid"
    )
    op.execute(
        "ALTER TABLE datasource_types "
        "DROP CONSTRAINT IF EXISTS fk_datasource_types_owner_user_id_users"
    )
    op.execute("DROP INDEX IF EXISTS idx_datasource_types_owner_sort")
    op.execute("DROP INDEX IF EXISTS uk_datasource_types_owner_code")
    op.drop_column("datasource_types", "owner_user_id")
    op.create_index("uk_datasource_types_code", "datasource_types", ["code"], unique=True)
    op.create_index("idx_datasource_types_sort", "datasource_types", ["sort_order"], unique=False)
