"""Loguru 日志初始化（技术栈详细说明 §2.4）。

- 统一格式：``{time} | {level} | {name}:{function}:{line} - {message}``
- 文件轮转：500 MB / 保留 10 天（由 ``settings.LOG_FILE`` 控制，空值只输出到 stderr）
- 全项目业务日志只用 Loguru，不使用标准库 logging（开发规范 §2.4）
"""
from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

from app.core.config import settings

LOG_FORMAT = "{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} - {message}"
ROTATION = "500 MB"
RETENTION = "10 days"


def setup_logging() -> None:
    """初始化日志 sink（可重复调用：先清空既有 sink）。"""
    logger.remove()
    logger.add(sys.stderr, level=settings.LOG_LEVEL, format=LOG_FORMAT)

    log_file = (settings.LOG_FILE or "").strip()
    if log_file:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        logger.add(
            str(path),
            level=settings.LOG_LEVEL,
            format=LOG_FORMAT,
            rotation=ROTATION,
            retention=RETENTION,
            encoding="utf-8",
        )

    logger.debug(
        "logging configured level={} file={}",
        settings.LOG_LEVEL,
        log_file or "<stderr only>",
    )


__all__ = ["LOG_FORMAT", "RETENTION", "ROTATION", "logger", "setup_logging"]
