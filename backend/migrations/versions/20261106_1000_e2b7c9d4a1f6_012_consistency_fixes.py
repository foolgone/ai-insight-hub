"""012 一致性修复（洞察落库 / 时间戳可空 / 清洗幂等）

对应《质量基建与一致性改进实施计划》阶段一：

- ``analysis_results.data_id`` 改为可空：洞察是「数据源级」结果，没有单条对话；
  同时补 ``(datasource_id, analysis_type, created_at DESC)`` 复合索引（报告取最新洞察）。
- ``cleaned_data.timestamp`` 改为可空：时间戳解析失败不再伪造「当前时间」（P1-6）。
- ``cleaned_data (raw_data_id, dialogue_id)`` 唯一索引：同一 raw_data 重跑不重复插入（P1-5）；
  建索引前先按 ``ctid`` 去重（保留物理最新的行）。

Revision ID: e2b7c9d4a1f6
Revises: d5e9b2c4f7a8
Create Date: 2026-11-06 10:00:00+08:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e2b7c9d4a1f6"
down_revision: Union[str, None] = "d5e9b2c4f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ① 洞察（数据源级结果）没有单条对话，data_id 必须可空
    op.alter_column(
        "analysis_results",
        "data_id",
        existing_type=sa.UUID(as_uuid=True),
        nullable=True,
    )
    # 报告查询：WHERE datasource_id = ? AND analysis_type = ? ORDER BY created_at DESC LIMIT 1
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_analysis_ds_type_created "
        "ON analysis_results (datasource_id, analysis_type, created_at DESC)"
    )

    # ② 时间戳缺失不再伪造当前时间
    op.alter_column(
        "cleaned_data",
        "timestamp",
        existing_type=sa.DateTime(),
        nullable=True,
    )

    # ③ 清洗幂等：先去重（保留每个键物理最新的一行）再建唯一索引
    op.execute(
        """
        DELETE FROM cleaned_data a
        USING cleaned_data b
        WHERE a.raw_data_id = b.raw_data_id
          AND a.dialogue_id = b.dialogue_id
          AND a.ctid < b.ctid
        """
    )
    op.create_index(
        "uk_cleaned_raw_dialogue",
        "cleaned_data",
        ["raw_data_id", "dialogue_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uk_cleaned_raw_dialogue", table_name="cleaned_data")

    # 回滚为 NOT NULL 前，把缺失时间补成迁移时刻（否则 ALTER 失败）
    op.execute("UPDATE cleaned_data SET timestamp = now() WHERE timestamp IS NULL")
    op.alter_column(
        "cleaned_data",
        "timestamp",
        existing_type=sa.DateTime(),
        nullable=False,
    )

    op.execute("DROP INDEX IF EXISTS idx_analysis_ds_type_created")
    # 旧代码不读取 data_id IS NULL 的洞察行；回滚时清理以保证 NOT NULL 可恢复
    op.execute("DELETE FROM analysis_results WHERE data_id IS NULL")
    op.alter_column(
        "analysis_results",
        "data_id",
        existing_type=sa.UUID(as_uuid=True),
        nullable=False,
    )
