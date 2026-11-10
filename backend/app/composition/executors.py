"""任务执行器注册表（组合根）。

把「``task_type`` → 入队函数」的映射集中在这里，让 ``task_service`` 不再
反向 import 各业务 service，消除循环依赖。

装配方式：首次调用 ``get_executor`` 时惰性导入各 service 并建立注册表；
新增任务类型时只需在这里加一条，不必修改 ``task_service``。
"""
from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import TaskNotRetryableError
from app.models import Report, Task

__all__ = ["Executor", "dispatch", "get_executor"]

Executor = Callable[[AsyncSession, Task], Awaitable[str]]

_REGISTRY: dict[str, Executor] | None = None


async def _enqueue_clean(_session: AsyncSession, task: Task) -> str:
    from app.composition import enqueue

    return enqueue.enqueue_clean(str(task.id))


async def _enqueue_evaluate(_session: AsyncSession, task: Task) -> str:
    from app.composition import enqueue

    return enqueue.enqueue_evaluation(str(task.id))


async def _enqueue_extract(_session: AsyncSession, task: Task) -> str:
    from app.composition import enqueue

    return enqueue.enqueue_extract(str(task.id))


async def _enqueue_insight(_session: AsyncSession, task: Task) -> str:
    from app.composition import enqueue

    return enqueue.enqueue_insight(str(task.id))


async def _enqueue_report(session: AsyncSession, task: Task) -> str:
    report_id = (task.params or {}).get("report_id")
    if not report_id:
        raise TaskNotRetryableError(
            details={"task_type": task.task_type, "reason": "missing_report_id"}
        )
    report = await session.get(Report, uuid.UUID(str(report_id)))
    if report is None:
        raise TaskNotRetryableError(
            details={"task_type": task.task_type, "reason": "report_not_found"}
        )
    from app.composition import enqueue

    return enqueue.enqueue_report(str(report.id))


def _build_registry() -> dict[str, Executor]:
    return {
        "clean": _enqueue_clean,
        "evaluate": _enqueue_evaluate,
        "extract": _enqueue_extract,
        "analyze": _enqueue_insight,
        "report": _enqueue_report,
    }


def get_executor(task_type: str) -> Executor | None:
    """按任务类型取执行器；未注册返回 ``None``。"""
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = _build_registry()
    return _REGISTRY.get(task_type)


async def dispatch(session: AsyncSession, task: Task) -> str:
    """按 ``task_type`` 重新入队（供 service 以回调形式注入）。"""
    executor = get_executor(task.task_type)
    if executor is None:
        raise TaskNotRetryableError(
            details={"task_type": task.task_type, "reason": "unsupported_type"}
        )
    return await executor(session, task)
