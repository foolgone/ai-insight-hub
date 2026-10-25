"""006 seed admin

按数据库设计 §6.3：种子管理员**不写入占位密码哈希**，密码哈希从环境变量读取；
未提供 ``SEED_ADMIN_EMAIL`` / ``SEED_ADMIN_PASSWORD_HASH`` 时本迁移为空操作（幂等）。

Revision ID: fdae51c51690
Revises: ae219b6b1866
Create Date: 2026-10-24 21:56:17.838634+08:00
"""
import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'fdae51c51690'
down_revision: Union[str, None] = 'ae219b6b1866'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INSERT_SQL = sa.text(
    """
    INSERT INTO users (email, password_hash, name, role)
    VALUES (:email, :password_hash, :name, 'admin')
    ON CONFLICT (email) DO NOTHING
    """
)


def upgrade() -> None:
    email = os.getenv("SEED_ADMIN_EMAIL", "").strip()
    password_hash = os.getenv("SEED_ADMIN_PASSWORD_HASH", "").strip()
    if not email or not password_hash:
        return
    op.get_bind().execute(
        _INSERT_SQL,
        {"email": email, "password_hash": password_hash, "name": "admin"},
    )


def downgrade() -> None:
    email = os.getenv("SEED_ADMIN_EMAIL", "").strip()
    if not email:
        return
    op.get_bind().execute(
        sa.text("DELETE FROM users WHERE email = :email AND role = 'admin'"),
        {"email": email},
    )
