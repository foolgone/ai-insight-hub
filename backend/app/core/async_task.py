"""Celery task async runner.

Celery (solo/prefork) would otherwise call ``asyncio.run`` per task, closing the
event loop after every task. Long-lived async resources cached on the worker
process — the SQLAlchemy asyncpg pool and the shared ``LLMClient`` httpx pool —
stay bound to that closed loop, so the next task fails with
``RuntimeError: Event loop is closed`` (observed as ``partial_failed`` runs).

``run_task`` keeps one event loop per worker process alive and reuses it for all
task coroutines. Resources created on the first task remain valid for later
tasks; the loop is closed only when the process exits.
"""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import TypeVar

T = TypeVar("T")

_loop: asyncio.AbstractEventLoop | None = None


def _get_loop() -> asyncio.AbstractEventLoop:
    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
    return _loop


def run_task(coro: Coroutine[object, object, T]) -> T:
    """Run a task coroutine on the worker's persistent event loop."""
    return _get_loop().run_until_complete(coro)


__all__ = ["run_task"]
