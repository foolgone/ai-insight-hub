"""测试数据工厂（factory_boy）。

约定：
- 工厂只负责构造未持久化的 ORM 实例，外键由测试显式传入（如 ``user_id=user.id``）；
- 持久化用 ``persist()``；集成测试的 ``db_session`` 会在用例结束后整体回滚；
- 默认值尽量使用可读常量，避免依赖随机数据导致的断言不稳定。
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import factory
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AnalysisResult,
    CleanedData,
    DataSource,
    KnowledgeBase,
    RawData,
    Task,
    User,
)

_FIXED_TIME = datetime(2026, 1, 1, 12, 0, 0)


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class UserFactory(factory.Factory):
    """users 表。"""

    class Meta:
        model = User

    id = factory.LazyFunction(_uuid)
    email = factory.Sequence(lambda n: f"user{n}@example.com")
    password_hash = "$2b$12$0123456789012345678901234567890123456789012345678901"
    name = "Test User"
    role = "user"
    is_active = True
    is_verified = True


class DataSourceFactory(factory.Factory):
    """data_sources 表（需显式传 user_id）。"""

    class Meta:
        model = DataSource

    id = factory.LazyFunction(_uuid)
    user_id = factory.LazyFunction(_uuid)
    name = factory.Sequence(lambda n: f"datasource-{n}")
    description = "测试数据源"
    type = "customer_service"
    status = "active"
    workflow_status = "created"


class RawDataFactory(factory.Factory):
    """raw_data 表。"""

    class Meta:
        model = RawData

    id = factory.LazyFunction(_uuid)
    datasource_id = factory.LazyFunction(_uuid)
    raw_content = factory.LazyFunction(
        lambda: {"text": "客户: 你好\n客服: 您好", "format": "csv", "encoding": "utf-8"}
    )
    status = "pending"


class CleanedDataFactory(factory.Factory):
    """cleaned_data 表。"""

    class Meta:
        model = CleanedData

    id = factory.LazyFunction(_uuid)
    datasource_id = factory.LazyFunction(_uuid)
    raw_data_id = factory.LazyFunction(_uuid)
    dialogue_id = factory.LazyFunction(_uuid)
    timestamp = factory.LazyFunction(lambda: _FIXED_TIME)
    user_message = "iPhone 14 多少钱？"
    ai_response = "5999 元起。"
    quality_score = 85.0
    issues: list[str] = []


class AnalysisResultFactory(factory.Factory):
    """analysis_results 表。"""

    class Meta:
        model = AnalysisResult

    id = factory.LazyFunction(_uuid)
    datasource_id = factory.LazyFunction(_uuid)
    data_id = factory.LazyFunction(_uuid)
    analysis_type = "quality"
    result = factory.LazyFunction(
        lambda: {
            "overall_score": 85,
            "dimensions": {"accuracy": {"score": 90, "issues": []}},
            "needs_review": False,
        }
    )
    agent_name = "evaluation_agent"
    confidence = 0.9


class KnowledgeBaseFactory(factory.Factory):
    """knowledge_base 表。"""

    class Meta:
        model = KnowledgeBase

    id = factory.LazyFunction(_uuid)
    datasource_id = factory.LazyFunction(_uuid)
    question = factory.Sequence(lambda n: f"常见问题 {n}")
    answer = "标准答案"
    category = "售后"
    source = "extracted"
    is_seed = False
    status = "active"


class TaskFactory(factory.Factory):
    """tasks 表。"""

    class Meta:
        model = Task

    id = factory.LazyFunction(_uuid)
    task_type = "clean"
    task_name = "清洗任务"
    status = "pending"
    progress = 0


async def persist(session: AsyncSession, *instances: object) -> None:
    """把工厂实例写入会话并 flush（不 commit，事务由 fixture 回滚）。"""
    session.add_all(instances)  # type: ignore[arg-type]
    await session.flush()


async def persist_cleaned(
    session: AsyncSession, datasource_id: uuid.UUID, **overrides: Any
) -> object:
    """持久化一条 cleaned_data，并自动创建其 ``raw_data``（T10 外键要求）。

    未显式传 ``raw_data_id`` 时先建一条 raw_data 再引用，避免孤儿行触发外键错误。
    """
    if "raw_data_id" not in overrides:
        raw = RawDataFactory(datasource_id=datasource_id)
        await persist(session, raw)
        overrides["raw_data_id"] = raw.id
    cleaned = CleanedDataFactory(datasource_id=datasource_id, **overrides)
    await persist(session, cleaned)
    return cleaned


def as_dict(**kwargs: Any) -> dict[str, Any]:
    """便捷构造请求体（测试用）。"""
    return dict(kwargs)


__all__ = [
    "AnalysisResultFactory",
    "CleanedDataFactory",
    "DataSourceFactory",
    "KnowledgeBaseFactory",
    "RawDataFactory",
    "TaskFactory",
    "UserFactory",
    "as_dict",
    "persist",
    "persist_cleaned",
]
