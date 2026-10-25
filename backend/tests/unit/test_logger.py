"""B-202 Loguru 日志配置测试。"""
from __future__ import annotations

from pathlib import Path

import pytest
from loguru import logger

from app.core.config import settings
from app.utils.logger import LOG_FORMAT, RETENTION, ROTATION, setup_logging

pytestmark = pytest.mark.unit


def test_log_contract_matches_tech_stack_doc() -> None:
    assert "{time" in LOG_FORMAT
    assert "{level}" in LOG_FORMAT
    assert "{name}" in LOG_FORMAT
    assert "{message}" in LOG_FORMAT
    assert ROTATION == "500 MB"
    assert RETENTION == "10 days"


def test_setup_logging_creates_file_and_writes(tmp_path: Path, monkeypatch) -> None:
    log_path = tmp_path / "logs" / "app.log"
    monkeypatch.setattr(settings, "LOG_FILE", str(log_path))
    monkeypatch.setattr(settings, "LOG_LEVEL", "DEBUG")

    try:
        setup_logging()
        logger.info("b202-logger-smoke")
        logger.remove()  # 关闭 sink 确保落盘

        content = log_path.read_text(encoding="utf-8")
        assert "b202-logger-smoke" in content
        assert "| INFO |" in content
        assert "app.utils.logger" in content or "tests.unit.test_logger" in content
    finally:
        monkeypatch.undo()
        setup_logging()


def test_setup_logging_is_idempotent(tmp_path: Path, monkeypatch) -> None:
    log_path = tmp_path / "logs" / "app.log"
    monkeypatch.setattr(settings, "LOG_FILE", str(log_path))

    try:
        setup_logging()
        logger.info("first")
        setup_logging()
        logger.info("second")
        logger.remove()

        content = log_path.read_text(encoding="utf-8")
        assert "first" in content
        assert "second" in content
    finally:
        monkeypatch.undo()
        setup_logging()
