"""022 M1-C 双指标持久化字段与回填

变更：
- ``rag_evaluation_results``：status 增加 ``invalid``；新增
  ``invalid_reason``、``derived_from_result_id``（自 FK）与索引；
- ``rag_evaluation_runs``：新增 ``evaluated_items`` / ``invalid_items`` /
  ``unprocessed_items``；备份旧 ``completed_items`` 并按 Item 优先级回填；
- 回填后 ``completed_items = evaluated_items``；
- 不回填 ``faithfulness_strict``；旧 v1/v2 行版本不变。

Revision ID: f3a9c2d7e1b4
Revises: d4e8b1c6f902
Create Date: 2026-11-19 18:00:00+08:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Connection

revision: str = "f3a9c2d7e1b4"
down_revision: Union[str, None] = "d4e8b1c6f902"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_BACKUP_TABLE = "rag_evaluation_runs_022_completed_backup"
_RESULT_TABLE = "rag_evaluation_results"
_RUN_TABLE = "rag_evaluation_runs"

# Item 优先级：failed > invalid > evaluated > skipped；
# unprocessed 只统计没有任何 result row 的 Item。
_BACKFILL_ITEM_SQL = """
WITH item_state AS (
    SELECT
        r.run_id,
        r.dataset_item_id,
        bool_or(
            r.status = 'failed' AND r.invalid_reason IS NULL
        ) AS has_failed,
        bool_or(
            r.status = 'invalid'
            OR (r.status = 'failed' AND r.invalid_reason IS NOT NULL)
        ) AS has_invalid,
        bool_or(r.status = 'evaluated') AS has_evaluated
    FROM rag_evaluation_results AS r
    GROUP BY r.run_id, r.dataset_item_id
),
item_bucket AS (
    SELECT
        run_id,
        CASE
            WHEN has_failed THEN 'failed'
            WHEN has_invalid THEN 'invalid'
            WHEN has_evaluated THEN 'evaluated'
            ELSE 'skipped'
        END AS bucket
    FROM item_state
),
run_counts AS (
    SELECT
        run_id,
        count(*) FILTER (WHERE bucket = 'evaluated') AS evaluated_items,
        count(*) FILTER (WHERE bucket = 'invalid')   AS invalid_items,
        count(*) FILTER (WHERE bucket = 'failed')    AS failed_items,
        count(*) FILTER (WHERE bucket = 'skipped')   AS skipped_items,
        count(*) AS distinct_items
    FROM item_bucket
    GROUP BY run_id
)
UPDATE rag_evaluation_runs AS run
SET evaluated_items   = COALESCE(c.evaluated_items, 0),
    invalid_items     = COALESCE(c.invalid_items, 0),
    failed_items      = COALESCE(c.failed_items, 0),
    skipped_items     = COALESCE(c.skipped_items, 0),
    unprocessed_items = GREATEST(
        run.total_items - COALESCE(c.distinct_items, 0), 0
    ),
    completed_items   = COALESCE(c.evaluated_items, 0)
FROM run_counts AS c
WHERE c.run_id = run.id
"""

_BACKFILL_NO_RESULT_SQL = f"""
UPDATE {_RUN_TABLE} AS run
SET evaluated_items   = 0,
    invalid_items     = 0,
    failed_items      = 0,
    skipped_items     = 0,
    unprocessed_items = run.total_items,
    completed_items   = 0
WHERE NOT EXISTS (
    SELECT 1 FROM {_RESULT_TABLE} AS r WHERE r.run_id = run.id
)
"""


def _backfill(bind: Connection) -> None:
    """按 Item 优先级回填 run 计数；测试可直接调用。"""
    bind.execute(sa.text(_BACKFILL_ITEM_SQL))
    bind.execute(sa.text(_BACKFILL_NO_RESULT_SQL))


def _drop_result_status_constraints() -> None:
    op.drop_constraint(
        "rag_eval_result_invalid_reason_status",
        _RESULT_TABLE,
        type_="check",
    )
    op.drop_constraint(
        "rag_eval_result_invalid_reason_required",
        _RESULT_TABLE,
        type_="check",
    )
    op.drop_constraint(
        "rag_eval_result_status_m1c",
        _RESULT_TABLE,
        type_="check",
    )


def upgrade() -> None:
    # ------------------------------------------------------------------ result
    op.drop_constraint(
        "rag_eval_result_status_valid",
        _RESULT_TABLE,
        type_="check",
    )
    op.add_column(
        _RESULT_TABLE,
        sa.Column("invalid_reason", sa.String(length=80), nullable=True),
    )
    op.add_column(
        _RESULT_TABLE,
        sa.Column(
            "derived_from_result_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_rag_evaluation_results_derived_from",
        _RESULT_TABLE,
        _RESULT_TABLE,
        ["derived_from_result_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_check_constraint(
        "rag_eval_result_status_m1c",
        _RESULT_TABLE,
        "status IN ('evaluated', 'skipped', 'invalid', 'failed')",
    )
    op.create_check_constraint(
        "rag_eval_result_invalid_reason_required",
        _RESULT_TABLE,
        "status <> 'invalid' OR invalid_reason IS NOT NULL",
    )
    op.create_check_constraint(
        "rag_eval_result_invalid_reason_status",
        _RESULT_TABLE,
        "invalid_reason IS NULL OR status IN ('invalid', 'failed')",
    )
    op.create_index(
        "idx_rag_evaluation_results_derived_from",
        _RESULT_TABLE,
        ["derived_from_result_id"],
    )

    # --------------------------------------------------------------------- run
    op.add_column(
        _RUN_TABLE,
        sa.Column("evaluated_items", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        _RUN_TABLE,
        sa.Column("invalid_items", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        _RUN_TABLE,
        sa.Column("unprocessed_items", sa.Integer(), nullable=False, server_default="0"),
    )

    # 旧 completed_items 备份，供 downgrade 恢复。
    op.execute(
        sa.text(
            f"""
            CREATE TABLE {_BACKUP_TABLE} AS
            SELECT id, completed_items FROM {_RUN_TABLE}
            """
        )
    )
    _backfill(op.get_bind())


def downgrade() -> None:
    bind = op.get_bind()
    invalid_or_strict = bind.execute(
        sa.text(
            f"""
            SELECT count(*) FROM {_RESULT_TABLE}
            WHERE status = 'invalid'
               OR invalid_reason IS NOT NULL
               OR metric_name = 'faithfulness_strict'
            """
        )
    ).scalar_one()
    if invalid_or_strict:
        raise RuntimeError(
            "cannot downgrade 022: invalid/faithfulness_strict rows exist; " "archive them first"
        )

    backup_exists = bind.execute(sa.text(f"SELECT to_regclass('{_BACKUP_TABLE}')")).scalar()
    if backup_exists is None:
        raise RuntimeError("cannot downgrade 022: completed_items backup table is missing")

    op.execute(
        sa.text(
            f"""
            UPDATE {_RUN_TABLE} AS run
            SET completed_items = backup.completed_items
            FROM {_BACKUP_TABLE} AS backup
            WHERE backup.id = run.id
            """
        )
    )

    _drop_result_status_constraints()
    op.drop_index("idx_rag_evaluation_results_derived_from", table_name=_RESULT_TABLE)
    op.drop_constraint(
        "fk_rag_evaluation_results_derived_from",
        _RESULT_TABLE,
        type_="foreignkey",
    )
    op.drop_column(_RESULT_TABLE, "derived_from_result_id")
    op.drop_column(_RESULT_TABLE, "invalid_reason")

    op.drop_column(_RUN_TABLE, "unprocessed_items")
    op.drop_column(_RUN_TABLE, "invalid_items")
    op.drop_column(_RUN_TABLE, "evaluated_items")

    op.create_check_constraint(
        "rag_eval_result_status_valid",
        _RESULT_TABLE,
        "status IN ('evaluated', 'skipped', 'failed')",
    )
    op.execute(sa.text(f"DROP TABLE {_BACKUP_TABLE}"))
