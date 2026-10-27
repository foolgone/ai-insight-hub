"""007 cleaned_data.raw_data_id 外键（T10）

Revision ID: 7a1c9b0d2e3f
Revises: fdae51c51690
Create Date: 2026-10-26 22:20:00+08:00

把 ``cleaned_data.raw_data_id`` 从「逻辑外键」升级为数据库层外键：
- 先清理历史孤儿行（raw_data 已不存在的 cleaned_data），否则建约束会失败；
- 再建 ``ON DELETE CASCADE`` 约束：原始数据被删除时级联清理清洗记录。
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7a1c9b0d2e3f"
down_revision: Union[str, None] = "fdae51c51690"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FK_NAME = "fk_cleaned_data_raw_data_id_raw_data"


def upgrade() -> None:
    # 1) 清理历史孤儿（生产库/开发库都可能存在）
    op.execute(
        """
        DELETE FROM cleaned_data cd
        WHERE NOT EXISTS (
            SELECT 1 FROM raw_data rd WHERE rd.id = cd.raw_data_id
        )
        """
    )
    # 2) 建立外键：raw_data 删除 → 级联删除对应 cleaned_data
    op.create_foreign_key(
        FK_NAME,
        source_table="cleaned_data",
        referent_table="raw_data",
        local_cols=["raw_data_id"],
        remote_cols=["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(FK_NAME, "cleaned_data", type_="foreignkey")
