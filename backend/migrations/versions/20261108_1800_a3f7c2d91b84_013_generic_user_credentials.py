"""013 通用用户凭据表（LLM + ASR 配置）

把 ``user_llm_credentials`` 从「一个用户一条 LLM Key」升级为
「一个用户每种 provider 一条凭据」，从而让语音转写（ASR）配置复用同一张表、
同一套 Fernet 加密与审计，不再写死在 ``.env``。

- 唯一索引：``uk_user_llm_credentials_user_id (user_id)`` →
  ``uk_user_llm_credentials_user_provider (user_id, provider)``；
- 新增 ``language``：ASR 识别语言（LLM 凭据留空）。

Revision ID: a3f7c2d91b84
Revises: e2b7c9d4a1f6
Create Date: 2026-11-08 18:00:00+08:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a3f7c2d91b84"
down_revision: Union[str, None] = "e2b7c9d4a1f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_llm_credentials",
        sa.Column("language", sa.String(length=10), nullable=True),
    )
    op.execute("DROP INDEX IF EXISTS uk_user_llm_credentials_user_id")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uk_user_llm_credentials_user_provider "
        "ON user_llm_credentials (user_id, provider)"
    )


def downgrade() -> None:
    # 回退前先清掉非 LLM 凭据，否则 (user_id) 唯一索引建不起来
    op.execute("DELETE FROM user_llm_credentials WHERE provider <> 'deepseek'")
    op.execute("DROP INDEX IF EXISTS uk_user_llm_credentials_user_provider")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uk_user_llm_credentials_user_id "
        "ON user_llm_credentials (user_id)"
    )
    op.drop_column("user_llm_credentials", "language")
