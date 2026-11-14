"""019 RAG 评测数据集：qa_datasets / qa_dataset_versions / qa_dataset_items

Phase 1 只新增表，不改任何既有表：
- ``qa_datasets``：数据集（按用户隔离，``(user_id, name)`` 唯一）；
- ``qa_dataset_versions``：版本（draft→published→archived，``(dataset_id, version)`` 唯一）；
- ``qa_dataset_items``：条目（``(version_id, item_key)`` 唯一；``gold_evidence`` 存快照）。

发布后不可变由服务层保证；DB 只做状态/取值约束。

Revision ID: b2f7c1d9e4a3
Revises: 9a4d2f8c6e15
Create Date: 2026-11-13 22:00:00+08:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b2f7c1d9e4a3"
down_revision: Union[str, None] = "9a4d2f8c6e15"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) 数据集
    op.create_table(
        "qa_datasets",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(length=20), nullable=False, server_default="mixed"),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "source_type IN ('doc', 'conv', 'mixed')", name="qa_dataset_source_type_valid"
        ),
    )
    op.create_index("uk_qa_datasets_user_name", "qa_datasets", ["user_id", "name"], unique=True)
    op.create_index("idx_qa_datasets_user_created", "qa_datasets", ["user_id", "created_at"])

    # 2) 版本
    op.create_table(
        "qa_dataset_versions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "dataset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("qa_datasets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("item_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("checksum", sa.String(length=64), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name="qa_dataset_version_status_valid",
        ),
    )
    op.create_index(
        "uk_qa_dataset_versions_dataset_version",
        "qa_dataset_versions",
        ["dataset_id", "version"],
        unique=True,
    )
    op.create_index(
        "idx_qa_dataset_versions_dataset_status",
        "qa_dataset_versions",
        ["dataset_id", "status"],
    )

    # 3) 条目
    op.create_table(
        "qa_dataset_items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("qa_dataset_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("item_key", sa.String(length=80), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("gold_answer", sa.Text(), nullable=True),
        sa.Column(
            "gold_evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("difficulty", sa.String(length=20), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=True),
        sa.Column("split", sa.String(length=10), nullable=False, server_default="test"),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "split IN ('train', 'valid', 'test')", name="qa_dataset_item_split_valid"
        ),
    )
    op.create_index(
        "uk_qa_dataset_items_version_key",
        "qa_dataset_items",
        ["version_id", "item_key"],
        unique=True,
    )
    op.create_index(
        "idx_qa_dataset_items_version_split", "qa_dataset_items", ["version_id", "split"]
    )
    op.create_index(
        "idx_qa_dataset_items_version_category",
        "qa_dataset_items",
        ["version_id", "category"],
    )


def downgrade() -> None:
    op.drop_index("idx_qa_dataset_items_version_category", table_name="qa_dataset_items")
    op.drop_index("idx_qa_dataset_items_version_split", table_name="qa_dataset_items")
    op.drop_index("uk_qa_dataset_items_version_key", table_name="qa_dataset_items")
    op.drop_table("qa_dataset_items")

    op.drop_index("idx_qa_dataset_versions_dataset_status", table_name="qa_dataset_versions")
    op.drop_index("uk_qa_dataset_versions_dataset_version", table_name="qa_dataset_versions")
    op.drop_table("qa_dataset_versions")

    op.drop_index("idx_qa_datasets_user_created", table_name="qa_datasets")
    op.drop_index("uk_qa_datasets_user_name", table_name="qa_datasets")
    op.drop_table("qa_datasets")
