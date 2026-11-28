"""023 M4-A tenant slice：tenants + tenant_id 回填

变更（仅租户列/索引，不改 JWT/Repository/存储）：
- 新建 ``tenants`` 并幂等插入默认租户；
- 核心业务表新增 nullable ``tenant_id``，按 user/父资源回填；
- 校验无 NULL / 父子一致后设置 NOT NULL（``audit_logs`` / ``llm_calls``
  保持 nullable，允许平台级记录）；
- 新增 tenant 复合索引；
- 业务表 server_default 指向默认租户，保证 flag=false 期间旧代码写入可用。

Revision ID: a7c4e9f2b6d1
Revises: f3a9c2d7e1b4
Create Date: 2026-11-25 20:00:00+08:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a7c4e9f2b6d1"
down_revision: Union[str, None] = "f3a9c2d7e1b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"
DEFAULT_TENANT_SQL = f"'{DEFAULT_TENANT_ID}'::uuid"

# 业务表：tenant_id 最终 NOT NULL。
BUSINESS_TABLES = [
    "users",
    "data_sources",
    "raw_data",
    "cleaned_data",
    "analysis_results",
    "knowledge_base",
    "knowledge_gaps",
    "tasks",
    "reports",
    "qa_datasets",
    "qa_dataset_versions",
    "qa_dataset_items",
    "rag_traces",
    "rag_evaluation_runs",
    "rag_evaluation_results",
]
# 平台级记录：允许 NULL。
PLATFORM_LOG_TABLES = ["audit_logs", "llm_calls"]

TENANT_INDEXES = [
    ("idx_users_tenant_created", "users", ["tenant_id", "created_at"]),
    ("idx_data_sources_tenant_user", "data_sources", ["tenant_id", "user_id"]),
    ("idx_data_sources_tenant_created", "data_sources", ["tenant_id", "created_at"]),
    ("idx_raw_data_tenant_datasource", "raw_data", ["tenant_id", "datasource_id"]),
    ("idx_cleaned_data_tenant_datasource", "cleaned_data", ["tenant_id", "datasource_id"]),
    (
        "idx_analysis_results_tenant_datasource",
        "analysis_results",
        ["tenant_id", "datasource_id"],
    ),
    ("idx_knowledge_base_tenant_datasource", "knowledge_base", ["tenant_id", "datasource_id"]),
    ("idx_knowledge_gaps_tenant_datasource", "knowledge_gaps", ["tenant_id", "datasource_id"]),
    ("idx_tasks_tenant_user_created", "tasks", ["tenant_id", "user_id", "created_at"]),
    ("idx_tasks_tenant_status", "tasks", ["tenant_id", "status"]),
    (
        "idx_reports_tenant_datasource_created",
        "reports",
        ["tenant_id", "datasource_id", "created_at"],
    ),
    ("idx_reports_tenant_user", "reports", ["tenant_id", "user_id"]),
    ("idx_qa_datasets_tenant_user", "qa_datasets", ["tenant_id", "user_id"]),
    ("idx_qa_dataset_versions_tenant_dataset", "qa_dataset_versions", ["tenant_id", "dataset_id"]),
    ("idx_qa_dataset_items_tenant_version", "qa_dataset_items", ["tenant_id", "version_id"]),
    ("idx_rag_traces_tenant_user_created", "rag_traces", ["tenant_id", "user_id", "created_at"]),
    (
        "idx_rag_evaluation_runs_tenant_user_created",
        "rag_evaluation_runs",
        ["tenant_id", "user_id", "created_at"],
    ),
    ("idx_rag_evaluation_runs_tenant_status", "rag_evaluation_runs", ["tenant_id", "status"]),
    ("idx_rag_evaluation_results_tenant_run", "rag_evaluation_results", ["tenant_id", "run_id"]),
    ("idx_audit_logs_tenant_created", "audit_logs", ["tenant_id", "created_at"]),
    ("idx_llm_calls_tenant_user_created", "llm_calls", ["tenant_id", "user_id", "created_at"]),
]

# 回填顺序：父表先行。
BACKFILL_SQL = [
    ("users", "UPDATE users SET tenant_id = :default WHERE tenant_id IS NULL"),
    (
        "data_sources",
        """
        UPDATE data_sources AS ds
        SET tenant_id = u.tenant_id
        FROM users AS u
        WHERE ds.user_id = u.id AND ds.tenant_id IS NULL
        """,
    ),
    (
        "raw_data",
        """
        UPDATE raw_data AS r
        SET tenant_id = ds.tenant_id
        FROM data_sources AS ds
        WHERE r.datasource_id = ds.id AND r.tenant_id IS NULL
        """,
    ),
    (
        "cleaned_data",
        """
        UPDATE cleaned_data AS c
        SET tenant_id = ds.tenant_id
        FROM data_sources AS ds
        WHERE c.datasource_id = ds.id AND c.tenant_id IS NULL
        """,
    ),
    (
        "analysis_results",
        """
        UPDATE analysis_results AS a
        SET tenant_id = ds.tenant_id
        FROM data_sources AS ds
        WHERE a.datasource_id = ds.id AND a.tenant_id IS NULL
        """,
    ),
    (
        "knowledge_base",
        """
        UPDATE knowledge_base AS k
        SET tenant_id = ds.tenant_id
        FROM data_sources AS ds
        WHERE k.datasource_id = ds.id AND k.tenant_id IS NULL
        """,
    ),
    (
        "knowledge_gaps",
        """
        UPDATE knowledge_gaps AS k
        SET tenant_id = ds.tenant_id
        FROM data_sources AS ds
        WHERE k.datasource_id = ds.id AND k.tenant_id IS NULL
        """,
    ),
    (
        "tasks",
        """
        UPDATE tasks AS t
        SET tenant_id = COALESCE(
            (SELECT u.tenant_id FROM users AS u WHERE u.id = t.user_id),
            (SELECT ds.tenant_id FROM data_sources AS ds WHERE ds.id = t.datasource_id),
            :default
        )
        WHERE t.tenant_id IS NULL
        """,
    ),
    (
        "reports",
        """
        UPDATE reports AS r
        SET tenant_id = COALESCE(
            (SELECT u.tenant_id FROM users AS u WHERE u.id = r.user_id),
            (SELECT ds.tenant_id FROM data_sources AS ds WHERE ds.id = r.datasource_id),
            :default
        )
        WHERE r.tenant_id IS NULL
        """,
    ),
    (
        "qa_datasets",
        """
        UPDATE qa_datasets AS d
        SET tenant_id = u.tenant_id
        FROM users AS u
        WHERE d.user_id = u.id AND d.tenant_id IS NULL
        """,
    ),
    (
        "qa_dataset_versions",
        """
        UPDATE qa_dataset_versions AS v
        SET tenant_id = d.tenant_id
        FROM qa_datasets AS d
        WHERE v.dataset_id = d.id AND v.tenant_id IS NULL
        """,
    ),
    (
        "qa_dataset_items",
        """
        UPDATE qa_dataset_items AS i
        SET tenant_id = v.tenant_id
        FROM qa_dataset_versions AS v
        WHERE i.version_id = v.id AND i.tenant_id IS NULL
        """,
    ),
    (
        "rag_traces",
        """
        UPDATE rag_traces AS t
        SET tenant_id = COALESCE(
            (SELECT u.tenant_id FROM users AS u WHERE u.id = t.user_id),
            (SELECT i.tenant_id FROM qa_dataset_items AS i WHERE i.id = t.dataset_item_id),
            :default
        )
        WHERE t.tenant_id IS NULL
        """,
    ),
    (
        "rag_evaluation_runs",
        """
        UPDATE rag_evaluation_runs AS r
        SET tenant_id = COALESCE(
            (SELECT u.tenant_id FROM users AS u WHERE u.id = r.user_id),
            (SELECT d.tenant_id FROM qa_datasets AS d WHERE d.id = r.dataset_id),
            :default
        )
        WHERE r.tenant_id IS NULL
        """,
    ),
    (
        "rag_evaluation_results",
        """
        UPDATE rag_evaluation_results AS res
        SET tenant_id = r.tenant_id
        FROM rag_evaluation_runs AS r
        WHERE res.run_id = r.id AND res.tenant_id IS NULL
        """,
    ),
    (
        "audit_logs",
        """
        UPDATE audit_logs AS a
        SET tenant_id = COALESCE(
            (SELECT u.tenant_id FROM users AS u WHERE u.id = a.user_id),
            :default
        )
        WHERE a.tenant_id IS NULL
        """,
    ),
    (
        "llm_calls",
        """
        UPDATE llm_calls AS l
        SET tenant_id = COALESCE(
            (SELECT u.tenant_id FROM users AS u WHERE u.id = l.user_id),
            (SELECT ds.tenant_id FROM data_sources AS ds WHERE ds.id = l.datasource_id),
            (SELECT t.tenant_id FROM tasks AS t WHERE t.id = l.task_id),
            :default
        )
        WHERE l.tenant_id IS NULL
        """,
    ),
]

PARENT_CHECKS = [
    ("raw_data", "datasource_id", "data_sources"),
    ("cleaned_data", "datasource_id", "data_sources"),
    ("analysis_results", "datasource_id", "data_sources"),
    ("knowledge_base", "datasource_id", "data_sources"),
    ("knowledge_gaps", "datasource_id", "data_sources"),
    ("qa_dataset_versions", "dataset_id", "qa_datasets"),
    ("qa_dataset_items", "version_id", "qa_dataset_versions"),
    ("rag_evaluation_results", "run_id", "rag_evaluation_runs"),
]


def _bind(sql: str):
    statement = sa.text(sql)
    if ":default" in sql:
        statement = statement.bindparams(default=DEFAULT_TENANT_ID)
    return statement


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("slug", sa.String(length=50), nullable=False),
        sa.Column(
            "status", sa.String(length=20), server_default=sa.text("'active'"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('active', 'suspended')", name=op.f("ck_tenants_status_valid")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tenants")),
    )
    op.create_index("idx_tenants_slug", "tenants", ["slug"], unique=True)
    op.create_index("idx_tenants_created_at", "tenants", ["created_at"])
    op.execute(
        sa.text(
            """
            INSERT INTO tenants (id, name, slug, status)
            VALUES (:id, :name, :slug, 'active')
            ON CONFLICT (id) DO NOTHING
            """
        ).bindparams(
            id=DEFAULT_TENANT_ID,
            name="默认租户",
            slug="default",
        )
    )

    for table in BUSINESS_TABLES + PLATFORM_LOG_TABLES:
        op.add_column(
            table,
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        )
        op.create_foreign_key(
            op.f(f"fk_{table}_tenant_id_tenants"),
            table,
            "tenants",
            ["tenant_id"],
            ["id"],
            ondelete="RESTRICT",
        )

    for _, sql in BACKFILL_SQL:
        op.execute(_bind(sql))

    for table in BUSINESS_TABLES:
        missing = (
            op.get_bind()
            .execute(sa.text(f"SELECT count(*) FROM {table} WHERE tenant_id IS NULL"))
            .scalar_one()
        )
        if missing:
            raise RuntimeError(f"tenant backfill incomplete: {table} missing={missing}")
    for child, fk, parent in PARENT_CHECKS:
        mismatched = (
            op.get_bind()
            .execute(
                sa.text(
                    f"""
                SELECT count(*)
                FROM {child} AS c
                JOIN {parent} AS p ON p.id = c.{fk}
                WHERE c.tenant_id IS DISTINCT FROM p.tenant_id
                """
                )
            )
            .scalar_one()
        )
        if mismatched:
            raise RuntimeError(f"tenant mismatch: {child}.{fk} != {parent}.tenant_id")

    for table in BUSINESS_TABLES:
        op.alter_column(
            table,
            "tenant_id",
            existing_type=postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text(DEFAULT_TENANT_SQL),
        )

    for name, table, columns in TENANT_INDEXES:
        op.create_index(name, table, columns)


def downgrade() -> None:
    for name, table, _ in reversed(TENANT_INDEXES):
        op.drop_index(name, table_name=table)

    for table in reversed(BUSINESS_TABLES + PLATFORM_LOG_TABLES):
        op.drop_constraint(op.f(f"fk_{table}_tenant_id_tenants"), table, type_="foreignkey")
        op.drop_column(table, "tenant_id")

    op.drop_index("idx_tenants_created_at", table_name="tenants")
    op.drop_index("idx_tenants_slug", table_name="tenants")
    op.drop_table("tenants")
