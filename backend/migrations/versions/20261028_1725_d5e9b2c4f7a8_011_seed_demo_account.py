"""011 seed demo account

只创建演示账号（业务数据由 ``scripts/seed_demo.py`` 负责，可重复执行并支持 --reset）。
幂等：``ON CONFLICT (email) DO UPDATE`` 在重放时恢复固定密码并解除软删。

Revision ID: d5e9b2c4f7a8
Revises: c4f8a1b2d3e6
Create Date: 2026-10-28 17:25:00+08:00
"""
import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from passlib.context import CryptContext

revision: str = "d5e9b2c4f7a8"
down_revision: Union[str, None] = "c4f8a1b2d3e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEMO_USER_ID = "00000000-0000-0000-0000-000000000001"
DEMO_EMAIL = "demo@example.com"
DEFAULT_DEMO_PASSWORD = "demo123"

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def upgrade() -> None:
    password = os.getenv("SEED_DEMO_PASSWORD", DEFAULT_DEMO_PASSWORD)
    password_hash = _pwd_context.hash(password)
    op.get_bind().execute(
        sa.text(
            """
            INSERT INTO users (id, email, password_hash, name, role, is_active, is_verified)
            VALUES (:id, :email, :password_hash, :name, 'user', true, true)
            ON CONFLICT (email) DO UPDATE
              SET password_hash = EXCLUDED.password_hash,
                  name = EXCLUDED.name,
                  is_active = true,
                  is_verified = true,
                  deleted_at = NULL,
                  updated_at = NOW()
            """
        ),
        {
            "id": DEMO_USER_ID,
            "email": DEMO_EMAIL,
            "password_hash": password_hash,
            "name": "演示用户",
        },
    )


def downgrade() -> None:
    # 演示业务数据由 seed_demo.py --reset 清理；此处仅删账号（级联删除其数据源）
    op.get_bind().execute(sa.text("DELETE FROM users WHERE email = :email"), {"email": DEMO_EMAIL})
