"""017 tasks 允许 structure（转写与切分拆成两个任务）

背景：媒体清洗原来是「转写 + 切分」一个任务，切分失败只能重跑整条清洗；
拆开后可以单独重试切分（转写结果复用、不重复计费），也便于按文件展示状态。

Revision ID: 7c1b5a9e2f43
Revises: 3e7a91c2d4b8
Create Date: 2026-11-12 09:00:00+08:00
"""
from typing import Sequence, Union

from alembic import op

revision: str = "7c1b5a9e2f43"
down_revision: Union[str, None] = "3e7a91c2d4b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TASK_TYPES = "'clean', 'structure', 'evaluate', 'extract', 'analyze', 'report'"
_TASK_TYPES_OLD = "'clean', 'evaluate', 'extract', 'analyze', 'report'"


def upgrade() -> None:
    op.drop_constraint("task_type_valid", "tasks", type_="check")
    op.create_check_constraint("task_type_valid", "tasks", f"task_type IN ({_TASK_TYPES})")


def downgrade() -> None:
    op.drop_constraint("task_type_valid", "tasks", type_="check")
    op.create_check_constraint("task_type_valid", "tasks", f"task_type IN ({_TASK_TYPES_OLD})")
