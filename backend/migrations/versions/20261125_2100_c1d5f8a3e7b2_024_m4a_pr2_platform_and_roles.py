"""024 M4-A PR-2：platform sentinel + 四角色迁移

变更（仅 migration/角色，不碰 JWT/Repository/存储）：
- ``tenants`` 增加 ``kind``（customer / platform）；默认租户 customer；
- 幂等插入 platform sentinel tenant（固定 UUID / slug='platform'），仅供
  platform_admin 内部任务/CLI，不出现在租户列表；
- ``users.role`` CHECK 扩展为 platform_admin / tenant_admin / user / viewer；
- 存量 admin → tenant_admin（不自动升 platform_admin）。

Revision ID: c1d5f8a3e7b2
Revises: a7c4e9f2b6d1
Create Date: 2026-11-25 21:00:00+08:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c1d5f8a3e7b2"
down_revision: Union[str, None] = "a7c4e9f2b6d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"
PLATFORM_TENANT_ID = "00000000-0000-0000-0000-000000000002"
ROLE_CHECK = "role IN ('platform_admin', 'tenant_admin', 'user', 'viewer')"
OLD_ROLE_CHECK = "role IN ('admin', 'user', 'viewer')"


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column(
            "kind",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'customer'"),
        ),
    )
    op.create_check_constraint(
        "kind_valid",
        "tenants",
        "kind IN ('customer', 'platform')",
    )
    op.create_index("idx_tenants_kind_status", "tenants", ["kind", "status"])

    # platform sentinel：只供 platform_admin 内部任务/CLI，不对外展示。
    op.execute(
        sa.text(
            """
            INSERT INTO tenants (id, name, slug, kind, status)
            VALUES (:id, :name, :slug, 'platform', 'active')
            ON CONFLICT (id) DO NOTHING
            """
        ).bindparams(
            id=PLATFORM_TENANT_ID,
            name="平台任务",
            slug="platform",
        )
    )

    op.drop_constraint(op.f("ck_users_role_valid"), "users", type_="check")
    op.execute(sa.text("UPDATE users SET role = 'tenant_admin' WHERE role = 'admin'"))
    op.create_check_constraint("role_valid", "users", ROLE_CHECK)


def downgrade() -> None:
    op.drop_constraint(op.f("ck_users_role_valid"), "users", type_="check")
    op.execute(
        sa.text(
            "UPDATE users SET role = 'admin' " "WHERE role IN ('tenant_admin', 'platform_admin')"
        )
    )
    op.create_check_constraint("role_valid", "users", OLD_ROLE_CHECK)

    op.execute(
        sa.text("DELETE FROM tenants WHERE id = :id AND slug = 'platform'").bindparams(
            id=PLATFORM_TENANT_ID
        )
    )
    op.drop_index("idx_tenants_kind_status", table_name="tenants")
    op.drop_constraint(op.f("ck_tenants_kind_valid"), "tenants", type_="check")
    op.drop_column("tenants", "kind")
