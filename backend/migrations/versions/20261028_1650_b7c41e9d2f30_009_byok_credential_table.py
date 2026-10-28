"""009 BYOK 凭据表（user_llm_credentials）

Revision ID: b7c41e9d2f30
Revises: 9b2d4f6a8c1e
Create Date: 2026-10-28 16:50:00+08:00

范围（业务收敛后的最小集）：
- 只新建 ``user_llm_credentials`` 一张表（一个用户一条凭据，密文落库）；
- **不**给 ``llm_calls`` 加 ``key_source``：生产 ``ALLOW_SERVER_KEY_FALLBACK=false``
  时不存在服务端 Key 调用，成本隔离字段没有消费方（见收敛稿 §3）。
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b7c41e9d2f30"
down_revision: Union[str, None] = "9b2d4f6a8c1e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_llm_credentials",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "provider", sa.String(length=50), server_default=sa.text("'deepseek'"), nullable=False
        ),
        sa.Column("base_url", sa.String(length=500), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("encrypted_api_key", sa.Text(), nullable=False),
        sa.Column("key_hint", sa.String(length=20), nullable=False),
        sa.Column(
            "status", sa.String(length=20), server_default=sa.text("'active'"), nullable=False
        ),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('active', 'invalid')", name="ck_user_llm_credentials_status_valid"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_user_llm_credentials_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_user_llm_credentials"),
    )
    op.create_index(
        "uk_user_llm_credentials_user_id",
        "user_llm_credentials",
        ["user_id"],
        unique=True,
    )
    op.create_index(
        "idx_user_llm_credentials_status", "user_llm_credentials", ["status"], unique=False
    )


def downgrade() -> None:
    op.drop_index("idx_user_llm_credentials_status", table_name="user_llm_credentials")
    op.drop_index("uk_user_llm_credentials_user_id", table_name="user_llm_credentials")
    op.drop_table("user_llm_credentials")
