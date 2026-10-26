"""Sentry 错误追踪（T7）。

约定：
- ``SENTRY_DSN`` 为空时**完全 no-op**，本地/测试不产生任何网络请求；
- 只在启动时初始化一次；未安装 ``sentry-sdk`` 时降级为日志告警；
- 业务异常仍走统一错误响应，Sentry 只负责「上报」，不改变 API 行为。
"""
from __future__ import annotations

from typing import Any

from loguru import logger

from app.core.config import settings

_initialized = False


def init_sentry() -> bool:
    """按配置初始化 Sentry；返回是否成功启用。"""
    global _initialized
    if _initialized:
        return True
    if not settings.SENTRY_DSN:
        logger.info("sentry disabled (SENTRY_DSN empty)")
        return False
    try:
        import sentry_sdk
    except ImportError:  # pragma: no cover - 依赖缺失时的防御
        logger.warning("sentry-sdk not installed, skip sentry init")
        return False
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.SENTRY_ENVIRONMENT,
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        send_default_pii=settings.SENTRY_SEND_DEFAULT_PII,
    )
    _initialized = True
    logger.info("sentry initialized env={}", settings.SENTRY_ENVIRONMENT)
    return True


def capture_exception(exc: BaseException, **extra: Any) -> None:
    """上报异常（未启用时静默跳过；上报失败绝不影响业务）。"""
    if not _initialized:
        return
    try:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            for key, value in extra.items():
                scope.set_extra(key, value)
            sentry_sdk.capture_exception(exc)
    except Exception:  # noqa: BLE001 - 可观测失败不能影响主流程
        logger.warning("sentry capture failed")


__all__ = ["capture_exception", "init_sentry"]
