"""成本追踪（B-306；成本管理 §3 / 数据库设计 §3.13 / D-03 幂等口径）。

- 成本 = (输入 token × P_IN + 输出 token × P_OUT) / 1_000_000，单价只来自配置；
- 每次 LLM 调用写一行 ``llm_calls``，幂等键 ``f"{task_id or 'adhoc'}:{attempt}"``，
  重复上报走 ``ON CONFLICT DO UPDATE``（不重复计费、失败回写同一行）；
- 成本对账只认本表聚合；Prometheus 只是进程内指标（见 ``09-可观测``）。
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.llm import LLMResponse, LLMUsage
from app.core.metrics import record_llm_call
from app.models import LlmCall

_TOKEN_SCALE = Decimal(1_000_000)
_COST_QUANT = Decimal("0.00000001")
_DEFAULT_SERVICE = "deepseek"

_price_warning_emitted = False


@dataclass(frozen=True)
class CostBreakdown:
    """单次调用的成本拆分。"""

    input_cost: Decimal
    output_cost: Decimal
    total_cost: Decimal


def compute_cost(
    usage: LLMUsage,
    *,
    price_input: float | Decimal | None = None,
    price_output: float | Decimal | None = None,
) -> CostBreakdown:
    """按配置单价计算成本；单价为 0 时首次调用告警（D-09）。"""
    global _price_warning_emitted

    raw_in = settings.LLM_PRICE_INPUT_PER_MTOK if price_input is None else price_input
    raw_out = settings.LLM_PRICE_OUTPUT_PER_MTOK if price_output is None else price_output
    p_in = Decimal(str(raw_in))
    p_out = Decimal(str(raw_out))

    if (p_in <= 0 or p_out <= 0) and not _price_warning_emitted:
        logger.warning(
            "LLM_PRICE_INPUT_PER_MTOK / LLM_PRICE_OUTPUT_PER_MTOK 未配置（0.0），"
            "成本将恒为 0；请按官方定价填写 .env（D-09）"
        )
        _price_warning_emitted = True

    input_cost = (Decimal(usage.input_tokens) * p_in / _TOKEN_SCALE).quantize(_COST_QUANT)
    output_cost = (Decimal(usage.output_tokens) * p_out / _TOKEN_SCALE).quantize(_COST_QUANT)
    return CostBreakdown(
        input_cost=input_cost,
        output_cost=output_cost,
        total_cost=(input_cost + output_cost).quantize(_COST_QUANT),
    )


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _day_start(now: datetime | None = None) -> datetime:
    current = now or datetime.now(timezone.utc)
    return current.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)


class CostTracker:
    """``llm_calls`` 的唯一写入口。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def idempotency_key(task_id: uuid.UUID | str | None, attempt: int) -> str:
        return f"{task_id or 'adhoc'}:{attempt}"

    async def track(
        self,
        *,
        response: LLMResponse,
        service: str = _DEFAULT_SERVICE,
        task_id: uuid.UUID | str | None = None,
        attempt: int = 0,
        user_id: uuid.UUID | None = None,
        datasource_id: uuid.UUID | None = None,
        agent_name: str | None = None,
        agent_version: str | None = None,
        key_source: str = "server",
    ) -> LlmCall:
        """写入一次成功的 LLM 调用（幂等 upsert）。"""
        usage = response.usage
        breakdown = compute_cost(usage)
        key = self.idempotency_key(task_id, attempt)
        values: dict[str, Any] = {
            "id": uuid.uuid4(),
            "user_id": user_id,
            "datasource_id": datasource_id,
            "task_id": uuid.UUID(str(task_id)) if task_id else None,
            "attempt": attempt,
            "idempotency_key": key,
            "service": service,
            "model": response.model,
            "agent_name": agent_name,
            "agent_version": agent_version,
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "total_tokens": usage.total_tokens,
            "input_cost": breakdown.input_cost,
            "output_cost": breakdown.output_cost,
            "total_cost": breakdown.total_cost,
            "duration": round(response.latency_ms / 1000, 6),
            "status": "success",
            "error_type": None,
            "error_message": None,
            "key_source": key_source,
        }
        row = await self._upsert(values)
        record_llm_call(
            model=response.model,
            agent_name=agent_name or "unknown",
            status="success",
            duration_seconds=response.latency_ms / 1000,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cost_usd=float(breakdown.total_cost),
        )
        return row

    async def record_failure(
        self,
        *,
        error: BaseException,
        model: str,
        service: str = _DEFAULT_SERVICE,
        task_id: uuid.UUID | str | None = None,
        attempt: int = 0,
        user_id: uuid.UUID | None = None,
        datasource_id: uuid.UUID | None = None,
        agent_name: str | None = None,
        agent_version: str | None = None,
        duration_seconds: float | None = None,
        key_source: str = "server",
    ) -> LlmCall:
        """把失败写回同一幂等键对应的行（D-03：按 task_id + 真实 attempt 回写）。"""
        zero = Decimal("0").quantize(_COST_QUANT)
        key = self.idempotency_key(task_id, attempt)
        values: dict[str, Any] = {
            "id": uuid.uuid4(),
            "user_id": user_id,
            "datasource_id": datasource_id,
            "task_id": uuid.UUID(str(task_id)) if task_id else None,
            "attempt": attempt,
            "idempotency_key": key,
            "service": service,
            "model": model,
            "agent_name": agent_name,
            "agent_version": agent_version,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "input_cost": zero,
            "output_cost": zero,
            "total_cost": zero,
            "duration": duration_seconds,
            "status": "failed",
            "error_type": type(error).__name__,
            "error_message": str(error)[:1000],
            "key_source": key_source,
        }
        row = await self._upsert(values)
        record_llm_call(
            model=model,
            agent_name=agent_name or "unknown",
            status="failed",
            duration_seconds=duration_seconds or 0.0,
        )
        return row

    async def _upsert(self, values: dict[str, Any]) -> LlmCall:
        update_fields = [
            "model",
            "agent_name",
            "agent_version",
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "input_cost",
            "output_cost",
            "total_cost",
            "duration",
            "status",
            "error_type",
            "error_message",
            "key_source",
        ]
        stmt: Any = pg_insert(LlmCall).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["idempotency_key"],
            set_={field: values[field] for field in update_fields},
        ).returning(LlmCall)
        row = (await self._session.execute(stmt)).scalar_one()
        await self._session.flush()
        return row

    async def get_daily_cost(
        self,
        *,
        user_id: uuid.UUID | None = None,
        now: datetime | None = None,
        only_server_key: bool = True,
    ) -> Decimal:
        """当日（UTC）成功调用成本合计。

        BYOK 成本隔离：默认只统计 ``key_source='server'``（用户自付的调用不触发降级）；
        用量报表用 ``get_usage_stats``，不过滤来源。
        """
        stmt = select(func.coalesce(func.sum(LlmCall.total_cost), 0)).where(
            LlmCall.status == "success",
            LlmCall.created_at >= _day_start(now),
        )
        if only_server_key:
            stmt = stmt.where(LlmCall.key_source == "server")
        if user_id is not None:
            stmt = stmt.where(LlmCall.user_id == user_id)
        value = await self._session.scalar(stmt)
        return Decimal(str(value or 0)).quantize(_COST_QUANT)

    async def get_usage_stats(
        self, *, days: int = 7, user_id: uuid.UUID | None = None
    ) -> dict[str, Any]:
        """近 N 天用量统计（调用数 / token / 成本 / 按模型）。"""
        since = _utc_now_naive() - timedelta(days=days)
        base_filters = [LlmCall.created_at >= since, LlmCall.status == "success"]
        if user_id is not None:
            base_filters.append(LlmCall.user_id == user_id)

        totals = (
            await self._session.execute(
                select(
                    func.count().label("calls"),
                    func.coalesce(func.sum(LlmCall.total_tokens), 0).label("tokens"),
                    func.coalesce(func.sum(LlmCall.total_cost), 0).label("cost"),
                ).where(*base_filters)
            )
        ).one()

        by_model_rows = (
            await self._session.execute(
                select(
                    LlmCall.model,
                    func.count().label("calls"),
                    func.coalesce(func.sum(LlmCall.total_cost), 0).label("cost"),
                )
                .where(*base_filters)
                .group_by(LlmCall.model)
            )
        ).all()

        return {
            "days": days,
            "calls": int(totals.calls or 0),
            "total_tokens": int(totals.tokens or 0),
            "total_cost": str(Decimal(str(totals.cost or 0)).quantize(_COST_QUANT)),
            "by_model": {
                str(row.model): {
                    "calls": int(row.calls or 0),
                    "cost": str(Decimal(str(row.cost or 0)).quantize(_COST_QUANT)),
                }
                for row in by_model_rows
            },
        }


__all__ = ["CostBreakdown", "CostTracker", "compute_cost"]
