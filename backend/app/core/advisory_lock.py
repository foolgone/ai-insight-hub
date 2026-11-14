"""PostgreSQL 会话级 Advisory Lock（Phase 3C）。

用于保证同一个评测 Run 只有一个 worker 执行：
- 锁绑定在**专用连接**上（`engine.connect()`），不经过业务 Session 的连接池归还；
- Run 全程持有该连接；业务事务用独立 Session 逐条提交，不影响锁；
- 释放必须在同一连接执行 `pg_advisory_unlock`，随后关闭连接；
- 进程崩溃 → 连接关闭 → PG 自动释放（无需额外清理）。
"""
from __future__ import annotations

import uuid

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.database import engine

_KEY_MASK = (1 << 63) - 1


def lock_key_for_run(run_id: uuid.UUID) -> int:
    """由 run_id 稳定派生 63 位整数 key（不同 Run 不冲突）。"""
    return int.from_bytes(run_id.bytes[:8], "big") & _KEY_MASK


class AdvisoryLock:
    """会话级 advisory lock 的获取/释放（非上下文管理器，便于显式控制生命周期）。"""

    def __init__(self, key: int) -> None:
        self.key = key
        self._conn: AsyncConnection | None = None

    @classmethod
    def for_run(cls, run_id: uuid.UUID) -> AdvisoryLock:
        return cls(lock_key_for_run(run_id))

    @property
    def held(self) -> bool:
        return self._conn is not None

    async def acquire(self) -> bool:
        if self._conn is not None:
            return True
        conn = await engine.connect()
        try:
            acquired = bool(
                await conn.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": self.key})
            )
        except Exception:
            await conn.close()
            raise
        if not acquired:
            await conn.close()
            return False
        self._conn = conn
        logger.debug("advisory lock acquired key={}", self.key)
        return True

    async def release(self) -> None:
        conn = self._conn
        if conn is None:
            return
        self._conn = None
        try:
            await conn.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": self.key})
            logger.debug("advisory lock released key={}", self.key)
        except Exception as exc:  # noqa: BLE001 - 释放失败不应掩盖业务结果
            logger.warning("advisory unlock failed key={} error={}", self.key, exc)
        finally:
            await conn.close()


__all__ = ["AdvisoryLock", "lock_key_for_run"]
