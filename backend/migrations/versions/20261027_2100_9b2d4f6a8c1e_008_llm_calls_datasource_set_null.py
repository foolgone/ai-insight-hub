"""008 llm_calls.datasource_id 改为 ON DELETE SET NULL

Revision ID: 9b2d4f6a8c1e
Revises: 7a1c9b0d2e3f
Create Date: 2026-10-27 21:00:00+08:00

背景：`llm_calls.datasource_id` 原外键无 ON DELETE 行为（NO ACTION），
导致任何产生过 LLM 调用的数据源在 `force=true` 物理删除时 500。
成本/审计记录需要保留，因此改为 `ON DELETE SET NULL`：
- 数据源物理删除后，llm_calls 行的 datasource_id 置空，成本记录不丢；
- 任务/数据源其余关联表保持 CASCADE（见 002/003）。
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9b2d4f6a8c1e"
down_revision: Union[str, None] = "7a1c9b0d2e3f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FK_NAME = "fk_llm_calls_datasource_id_data_sources"


def upgrade() -> None:
    op.drop_constraint(FK_NAME, "llm_calls", type_="foreignkey")
    op.create_foreign_key(
        FK_NAME,
        source_table="llm_calls",
        referent_table="data_sources",
        local_cols=["datasource_id"],
        remote_cols=["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(FK_NAME, "llm_calls", type_="foreignkey")
    op.create_foreign_key(
        FK_NAME,
        source_table="llm_calls",
        referent_table="data_sources",
        local_cols=["datasource_id"],
        remote_cols=["id"],
    )
