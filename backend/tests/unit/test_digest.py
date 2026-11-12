"""周报（#5）：正文格式、未配置 SMTP 的 no-op。"""
from __future__ import annotations

from datetime import datetime

from app.core.config import settings
from app.services import notification_service
from app.tasks.digest import render_digest

PAYLOAD = {
    "since": datetime(2026, 11, 5, 9, 0),
    "until": datetime(2026, 11, 12, 9, 0),
    "tasks_completed": 12,
    "tasks_failed": 2,
    "by_type": {"clean": 8, "evaluate": 4},
    "cost": 0.1234,
    "calls": 30,
    "open_gaps": 5,
}


def test_render_digest_contains_key_sections() -> None:
    body = render_digest(PAYLOAD)

    assert "2026-11-05 ~ 2026-11-12" in body
    assert "完成：12    失败：2" in body
    assert "clean 8" in body and "evaluate 4" in body
    assert "$0.1234" in body
    assert "待处理盲区：5 条" in body


def test_send_email_is_noop_without_smtp(monkeypatch) -> None:
    monkeypatch.setattr(settings, "SMTP_USER", "")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "")

    assert notification_service.smtp_configured() is False
    assert notification_service.send_email("主题", "正文") is False
