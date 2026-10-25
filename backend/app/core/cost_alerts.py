"""成本告警（B-308；成本管理 §5.1 —— 阈值唯一来源在 ``degradation.THRESHOLDS``）。"""
from __future__ import annotations

from app.core.degradation import (
    THRESHOLDS,
    DegradationLevel,
    level_for_ratio,
)


class CostAlertManager:
    """按当日成本/预算比例给出告警等级。"""

    # 键为等级名，便于日志/告警系统按名匹配
    ALERT_THRESHOLDS: dict[str, float] = {
        level.value: threshold for level, threshold in THRESHOLDS.items()
    }

    @staticmethod
    def level_for_ratio(ratio: float) -> DegradationLevel:
        return level_for_ratio(ratio)

    @staticmethod
    def should_notify(level: DegradationLevel) -> bool:
        return level is not DegradationLevel.NORMAL


__all__ = ["CostAlertManager"]
