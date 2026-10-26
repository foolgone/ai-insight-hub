"""T7 Sentry 封装测试（未配置 DSN 时 no-op；配置后调用 SDK）。"""
from __future__ import annotations

import sys
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from app.core import sentry as sentry_module
from app.core.config import settings

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch):
    monkeypatch.setattr(sentry_module, "_initialized", False)
    yield
    monkeypatch.setattr(sentry_module, "_initialized", False)


def test_init_sentry_disabled_without_dsn(monkeypatch) -> None:
    monkeypatch.setattr(settings, "SENTRY_DSN", "")

    assert sentry_module.init_sentry() is False
    assert sentry_module.capture_exception(RuntimeError("boom")) is None


def test_init_sentry_initializes_sdk(monkeypatch) -> None:
    events: list[tuple[str, object]] = []

    @contextmanager
    def _push_scope():
        yield SimpleNamespace(set_extra=lambda key, value: events.append((key, value)))

    fake_sdk = SimpleNamespace(
        init=lambda **kwargs: events.append(("init", kwargs)),
        capture_exception=lambda exc: events.append(("capture", exc)),
        push_scope=_push_scope,
    )
    monkeypatch.setitem(sys.modules, "sentry_sdk", fake_sdk)
    monkeypatch.setattr(settings, "SENTRY_DSN", "https://example.invalid/1")
    monkeypatch.setattr(settings, "SENTRY_ENVIRONMENT", "test")

    assert sentry_module.init_sentry() is True
    sentry_module.capture_exception(ValueError("bad"), task_id="t-1")

    assert events[0][0] == "init"
    assert events[0][1]["environment"] == "test"
    assert ("task_id", "t-1") in events
    assert events[-1][0] == "capture"
    assert isinstance(events[-1][1], ValueError)
