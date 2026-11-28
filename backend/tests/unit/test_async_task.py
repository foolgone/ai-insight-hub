"""Celery async runner: one persistent event loop per worker process (P1-0)."""

import asyncio

import pytest

from app.core import async_task


async def _loop_id() -> int:
    return id(asyncio.get_running_loop())


async def _boom() -> None:
    raise RuntimeError("boom")


def test_run_task_returns_result():
    assert async_task.run_task(asyncio.sleep(0, result=42)) == 42


def test_run_task_reuses_one_loop_across_tasks():
    first = async_task.run_task(_loop_id())
    second = async_task.run_task(_loop_id())
    assert first == second


def test_run_task_propagates_errors_and_keeps_loop_usable():
    with pytest.raises(RuntimeError, match="boom"):
        async_task.run_task(_boom())
    assert async_task.run_task(_loop_id()) == async_task.run_task(_loop_id())
