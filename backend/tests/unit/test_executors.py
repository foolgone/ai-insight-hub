"""任务执行器注册表单测（composition/executors）。"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.composition import executors
from app.core.exceptions import TaskNotRetryableError

pytestmark = pytest.mark.unit


def test_known_task_types_registered() -> None:
    for task_type in ("clean", "evaluate", "extract", "analyze", "report"):
        assert callable(executors.get_executor(task_type))
    assert executors.get_executor("unknown") is None


def test_registry_is_built_once() -> None:
    first = executors.get_executor("clean")
    second = executors.get_executor("clean")
    assert first is second


@pytest.mark.asyncio
async def test_report_requires_report_id() -> None:
    task = SimpleNamespace(task_type="report", params={})
    with pytest.raises(TaskNotRetryableError):
        await executors._enqueue_report(None, task)  # type: ignore[arg-type]
