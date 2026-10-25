"""B-308 降级等级 / 动作 / 成本告警单测（D-09：不切模型）。"""
from __future__ import annotations

import pytest

from app.core.config import settings
from app.core.cost_alerts import CostAlertManager
from app.core.degradation import (
    ACTIONS,
    DegradationConfig,
    DegradationLevel,
    level_for_ratio,
)
from app.core.degradation_manager import DegradationManager

pytestmark = pytest.mark.unit


def test_alert_thresholds_are_single_source() -> None:
    assert CostAlertManager.ALERT_THRESHOLDS == {
        "warning": 0.80,
        "throttled": 0.90,
        "degraded": 1.00,
        "stopped": 1.20,
    }


@pytest.mark.parametrize(
    ("ratio", "expected"),
    [
        (0.0, DegradationLevel.NORMAL),
        (0.79, DegradationLevel.NORMAL),
        (0.80, DegradationLevel.WARNING),
        (0.89, DegradationLevel.WARNING),
        (0.90, DegradationLevel.THROTTLED),
        (0.99, DegradationLevel.THROTTLED),
        (1.00, DegradationLevel.DEGRADED),
        (1.19, DegradationLevel.DEGRADED),
        (1.20, DegradationLevel.STOPPED),
        (2.00, DegradationLevel.STOPPED),
    ],
)
def test_level_boundaries(ratio: float, expected: DegradationLevel) -> None:
    assert level_for_ratio(ratio) is expected
    assert CostAlertManager.level_for_ratio(ratio) is expected


def test_actions_per_level() -> None:
    assert ACTIONS[DegradationLevel.NORMAL].qps == 60
    assert ACTIONS[DegradationLevel.THROTTLED].qps == 30
    assert ACTIONS[DegradationLevel.DEGRADED].pause_background_tasks is True
    assert ACTIONS[DegradationLevel.STOPPED].reject_requests is True
    assert ACTIONS[DegradationLevel.STOPPED].features == ()
    assert DegradationConfig.action_for(DegradationLevel.NORMAL) is (
        ACTIONS[DegradationLevel.NORMAL]
    )


def test_degraded_model_not_switched_when_unconfigured(monkeypatch) -> None:
    monkeypatch.setattr(settings, "DEGRADED_LLM_MODEL", "")

    assert DegradationManager.should_use_degraded_model(DegradationLevel.DEGRADED) is False
    assert (
        DegradationManager.model_for_level(DegradationLevel.DEGRADED) == settings.DEFAULT_LLM_MODEL
    )


def test_degraded_model_switched_when_configured(monkeypatch) -> None:
    monkeypatch.setattr(settings, "DEGRADED_LLM_MODEL", "degraded-model")

    assert DegradationManager.should_use_degraded_model(DegradationLevel.DEGRADED)
    assert DegradationManager.model_for_level(DegradationLevel.DEGRADED) == "degraded-model"


def test_stopped_and_qps() -> None:
    assert DegradationManager.is_service_stopped(DegradationLevel.STOPPED) is True
    assert DegradationManager.is_service_stopped(DegradationLevel.DEGRADED) is False
    assert DegradationManager.qps_for(DegradationLevel.STOPPED) == 0
    assert DegradationManager.qps_for(DegradationLevel.THROTTLED) == 30


async def test_manager_without_session_returns_normal() -> None:
    manager = DegradationManager()

    level = await manager.get_level()

    assert level is DegradationLevel.NORMAL


async def test_manager_zero_daily_limit_returns_normal(monkeypatch) -> None:
    monkeypatch.setattr(settings, "DAILY_COST_LIMIT", 0.0)
    manager = DegradationManager()  # 无 session 也不报错

    level = await manager.get_level()

    assert level is DegradationLevel.NORMAL
