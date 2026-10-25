"""Alembic 迁移环境。

数据库连接串统一来自 app.core.config.settings.DATABASE_URL（不在 alembic.ini 里写死）。
Alembic 使用同步驱动，故把 asyncpg 方言替换掉。
"""
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# 让 alembic 能 import app.*
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402
from app.models.base import Base  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 同步连接串（去掉 asyncpg 方言）
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL.replace("+asyncpg", ""))

# 表结构事实源：app/models（模型在 app/models/__init__.py 统一登记）
target_metadata = Base.metadata

# 手工维护的表达式索引（pg_trgm）：见迁移 002
_MANUAL_INDEXES = {"idx_cleaned_data_search", "idx_kb_search"}


def _included_tables() -> set[str] | None:
    """按域生成迁移时用：ALEMBIC_TABLES=a,b 只处理指定表。

    仅用于 ``alembic revision --autogenerate`` 的分批生成；日常迁移
    （``upgrade head``）不设置该变量，行为不变。
    """
    raw = os.getenv("ALEMBIC_TABLES", "").strip()
    if not raw:
        return None
    return {name.strip() for name in raw.split(",") if name.strip()}


def include_object(obj, name, type_, reflected, compare_to) -> bool:  # noqa: ANN001
    tables = _included_tables()
    if tables is not None and type_ == "table":
        return name in tables
    # 表达式 GIN(pg_trgm) 索引由迁移 002 手工创建，SQLAlchemy metadata 无法表达，
    # 在 autogenerate 比较中忽略，避免被误判为「待删除」。
    if type_ == "index" and name in _MANUAL_INDEXES:
        return False
    return True


def run_migrations_offline() -> None:
    """离线模式：只生成 SQL，不连库"""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：直连数据库执行迁移"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
