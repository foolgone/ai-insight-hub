"""降级等级与动作（B-308；06-成本超限降级策略 §2）。

五档唯一阈值（全项目只读此处）：warning 0.80 / throttled 0.90 / degraded 1.00 / stopped 1.20。
``DEGRADED_LLM_MODEL`` 未配置时不切换模型（D-09：只告警、不降级到备选模型）。
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

ALL_FEATURES: tuple[str, ...] = ("clean", "evaluate", "extract", "analyze", "report")


class DegradationLevel(str, Enum):
    NORMAL = "normal"
    WARNING = "warning"
    THROTTLED = "throttled"
    DEGRADED = "degraded"
    STOPPED = "stopped"


@dataclass(frozen=True)
class DegradationAction:
    qps: int
    features: tuple[str, ...]
    pause_background_tasks: bool
    reject_requests: bool


THRESHOLDS: dict[DegradationLevel, float] = {
    DegradationLevel.WARNING: 0.80,
    DegradationLevel.THROTTLED: 0.90,
    DegradationLevel.DEGRADED: 1.00,
    DegradationLevel.STOPPED: 1.20,
}

ACTIONS: dict[DegradationLevel, DegradationAction] = {
    DegradationLevel.NORMAL: DegradationAction(60, ALL_FEATURES, False, False),
    DegradationLevel.WARNING: DegradationAction(60, ALL_FEATURES, False, False),
    DegradationLevel.THROTTLED: DegradationAction(
        30, ("clean", "evaluate", "extract"), False, False
    ),
    DegradationLevel.DEGRADED: DegradationAction(10, ("clean", "evaluate"), True, False),
    DegradationLevel.STOPPED: DegradationAction(0, (), True, True),
}


def level_for_ratio(ratio: float) -> DegradationLevel:
    """按「当日成本 / 日预算」比例映射等级。"""
    if ratio >= THRESHOLDS[DegradationLevel.STOPPED]:
        return DegradationLevel.STOPPED
    if ratio >= THRESHOLDS[DegradationLevel.DEGRADED]:
        return DegradationLevel.DEGRADED
    if ratio >= THRESHOLDS[DegradationLevel.THROTTLED]:
        return DegradationLevel.THROTTLED
    if ratio >= THRESHOLDS[DegradationLevel.WARNING]:
        return DegradationLevel.WARNING
    return DegradationLevel.NORMAL


class DegradationConfig:
    """降级配置快照（阈值/动作均只读）。"""

    thresholds: dict[DegradationLevel, float] = THRESHOLDS
    actions: dict[DegradationLevel, DegradationAction] = ACTIONS

    @classmethod
    def action_for(cls, level: DegradationLevel) -> DegradationAction:
        return cls.actions[level]


__all__ = [
    "ACTIONS",
    "ALL_FEATURES",
    "THRESHOLDS",
    "DegradationAction",
    "DegradationConfig",
    "DegradationLevel",
    "level_for_ratio",
]
