"""SQLAlchemy ORM 基类。

- 统一约束/索引命名约定（便于 Alembic 生成稳定迁移名）；
- 业务表只继承 ``Base``，禁止手写 DDL；
- 表结构唯一事实源：``docs/03-architecture/03-数据库设计.md``。
"""
from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
