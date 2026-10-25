"""降级管理器（B-308）。

- 等级由「当日成本 / ``DAILY_COST_LIMIT``」决定（成本追踪只认 ``llm_calls``）；
- ``DEGRADED_LLM_MODEL`` 未配置时**不切换模型**（D-09 产品决定：只告警，不降级模型）；
- ``STOPPED`` 时上游应拒绝新的 AI 请求（返回 429 / 跳过任务）。
"""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.cost_alerts import CostAlertManager
from app.core.cost_tracker import CostTracker
from app.core.degradation import (
    DegradationAction,
    DegradationConfig,
    DegradationLevel,
)


class DegradationManager:
    """按用户当日成本判定降级等级。"""

    def __init__(self, session: AsyncSession | None = None) -> None:
        self._session = session

    async def get_cost_ratio(self, *, user_id: uuid.UUID | None = None) -> float:
        """当日成本 / 日预算（无会话或预算≤0 时返回 0）。"""
        limit = float(settings.DAILY_COST_LIMIT)
        if self._session is None or limit <= 0:
            return 0.0
        cost = await CostTracker(self._session).get_daily_cost(user_id=user_id)
        return float(cost) / limit

    async def get_level(self, *, user_id: uuid.UUID | None = None) -> DegradationLevel:
        ratio = await self.get_cost_ratio(user_id=user_id)
        return CostAlertManager.level_for_ratio(ratio)

    @staticmethod
    def should_use_degraded_model(level: DegradationLevel) -> bool:
        """是否切换到降级模型（D-09：空配置视为不启用）。"""
        return level is DegradationLevel.DEGRADED and bool(settings.DEGRADED_LLM_MODEL.strip())

    @staticmethod
    def model_for_level(level: DegradationLevel) -> str:
        if DegradationManager.should_use_degraded_model(level):
            return settings.DEGRADED_LLM_MODEL.strip()
        return settings.DEFAULT_LLM_MODEL

    @staticmethod
    def is_service_stopped(level: DegradationLevel) -> bool:
        return level is DegradationLevel.STOPPED

    @staticmethod
    def action_for(level: DegradationLevel) -> DegradationAction:
        return DegradationConfig.action_for(level)

    @staticmethod
    def qps_for(level: DegradationLevel) -> int:
        return DegradationConfig.action_for(level).qps


__all__ = ["DegradationManager"]
