"""Agent 基座（B-310；Agent 详细设计 §1.2 —— 框架无关版，ADR-001）。

对外契约（保持不变）：
- ``AgentConfig`` / ``AgentResult`` / ``AgentError`` 异常树；
- ``BaseAgent(config).invoke(input_data, ...) -> AgentResult``；
- 5 个抽象方法：``_init_tools`` / ``_load_prompt`` / ``_create_agent`` /
  ``_validate_input`` / ``_validate_output``。

``invoke`` 流水线：
输入校验 → 降级判定（STOPPED 拒绝）→ 重试 + 超时（``async_retry``）→
结构化输出（可选 ``output_schema``）→ 输出校验 → 成本/指标落库 → 返回 ``AgentResult``。
异常一律收敛为 ``AgentResult(success=False)``，不向调用方抛出（D-01）。
"""
from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from loguru import logger
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.guards import neutralize_payload
from app.core.config import settings
from app.core.cost_tracker import CostTracker, compute_cost
from app.core.degradation import DegradationLevel
from app.core.degradation_manager import DegradationManager
from app.core.exceptions import LLMCredentialInvalidError, LLMCredentialNotConfiguredError
from app.core.llm import LLMAuthenticationError, LLMClient, LLMResponse, LLMUsage, Message
from app.core.metrics import record_agent_invocation
from app.core.retry_config import RetryConfig
from app.utils.retry import async_retry
from app.utils.retry_guard import CostAwareRetryGuard

# --------------------------------------------------------------------------- 异常树


class AgentError(Exception):
    """Agent 异常基类；``retryable`` 供重试策略判定。"""

    retryable = False


class AgentInputError(AgentError):
    """输入不合法（不可重试）。"""


class AgentOutputError(AgentError):
    """输出不合法（不可重试）。"""


class AgentTimeoutError(AgentError):
    retryable = True


class AgentExecutionError(AgentError):
    retryable = True


class AgentDegradedError(AgentExecutionError):
    """服务因成本超限被停止（不可重试）。"""

    retryable = False


class CleaningError(AgentError):
    """清洗 Agent 业务异常。"""


class EvaluationError(AgentError):
    """评估 Agent 业务异常。"""


class ExtractionError(AgentError):
    """提取 Agent 业务异常。"""


class InsightError(AgentError):
    """洞察 Agent 业务异常。"""


class ReportError(AgentError):
    """报告 Agent 业务异常。"""


# --------------------------------------------------------------------------- 配置/结果


@dataclass
class AgentConfig:
    """Agent 配置（模型 id 不写死，默认取全局配置）。"""

    name: str
    version: str = "v1.0.0"
    model: str = field(default_factory=lambda: settings.DEFAULT_LLM_MODEL)
    temperature: float = field(default_factory=lambda: settings.DEFAULT_TEMPERATURE)
    max_tokens: int = field(default_factory=lambda: settings.DEFAULT_MAX_TOKENS)
    timeout: float = field(default_factory=lambda: float(settings.DEFAULT_TIMEOUT))
    max_retries: int = 3
    retry_base_delay: float = 1.0
    max_retry_tokens: int = 20_000


@dataclass
class AgentResult:
    """Agent 执行结果（唯一对外返回类型）。"""

    success: bool
    data: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    duration: float = 0.0
    token_usage: dict[str, int] = field(default_factory=lambda: {"input": 0, "output": 0})
    cost: Decimal = Decimal("0")


# --------------------------------------------------------------------------- 基类


class BaseAgent(ABC):
    """所有 Agent 的基类。"""

    #: 子类可声明输出 Schema；声明后 invoke 会走结构化输出兜底
    output_schema: type[BaseModel] | None = None

    def __init__(self, config: AgentConfig, *, llm: LLMClient | None = None) -> None:
        self.config = config
        self.llm = llm or LLMClient(model=config.model, timeout=config.timeout)
        self.tools: dict[str, Any] = {}
        self._prompt: str | None = None
        self._init_tools()

    # -- 子类必须实现 -----------------------------------------------------
    @abstractmethod
    def _init_tools(self) -> None:
        """初始化工具（纯 Python 函数，不做 LLM tool-calling）。"""

    @abstractmethod
    def _load_prompt(self) -> str:
        """加载 system prompt（来自 ``app/prompts/`` 资产）。"""

    @abstractmethod
    def _create_agent(self, input_data: Mapping[str, Any]) -> Sequence[Message]:
        """组装本次调用的 messages（框架无关）。"""

    @abstractmethod
    def _validate_input(self, input_data: Mapping[str, Any]) -> None:
        """输入校验；不合法抛 ``AgentInputError``。"""

    @abstractmethod
    def _validate_output(self, data: Any) -> dict[str, Any]:
        """输出校验/归一化；不合法抛 ``AgentOutputError``。"""

    # -- 对外唯一入口 -----------------------------------------------------
    async def invoke(
        self,
        input_data: Mapping[str, Any],
        *,
        session: AsyncSession | None = None,
        task_id: uuid.UUID | str | None = None,
        user_id: uuid.UUID | None = None,
        datasource_id: uuid.UUID | None = None,
    ) -> AgentResult:
        """执行 Agent；任何异常都收敛为 ``AgentResult(success=False)``。"""
        started = time.perf_counter()
        model = self.config.model
        level = DegradationLevel.NORMAL
        attempts = 0
        token_usage = {"input": 0, "output": 0}
        guard_hits: list[str] = []

        # ── BYOK：解析本次调用使用的凭据（必须在 try 之外，异常向上冒泡） ──
        # 只有"有 user_id + session"且未开 fallback 时才要求用户 Key；
        # session 为 None 的 POC/单测路径保持现状（走 self.llm）。
        byok_key: str | None = None
        agent_llm = self.llm
        if not settings.ALLOW_SERVER_KEY_FALLBACK and user_id is not None and session is not None:
            # 延迟 import，避免 agents 与 services 的模块级循环依赖
            from app.services.credential_service import credential_service

            credential = await credential_service.get_credential(session, user_id)
            if credential is None:
                raise LLMCredentialNotConfiguredError()
            if credential.status != "active":
                raise LLMCredentialInvalidError()
            byok_key = credential_service.decrypt_credential(credential)
            agent_llm = LLMClient(
                model=self.config.model,
                timeout=self.config.timeout,
                api_key=byok_key,
            )
        # ── END BYOK ──
        key_source = "user" if byok_key is not None else "server"

        try:
            # 输入来自用户数据（不可信）：先中和显式 Prompt 注入，再校验/组装 messages
            sanitized_input, guard_hits = neutralize_payload(input_data)
            if guard_hits:
                logger.warning(
                    "prompt injection suspected agent={} hits={}",
                    self.config.name,
                    guard_hits[:5],
                )
            self._validate_input(sanitized_input)

            level = await self._resolve_level(session, user_id)
            if DegradationManager.is_service_stopped(level):
                raise AgentDegradedError("AI service stopped: daily cost limit reached")
            model = DegradationManager.model_for_level(level)

            messages = list(self._create_agent(sanitized_input))
            retry_config = RetryConfig(
                max_retries=self.config.max_retries,
                initial_delay=self.config.retry_base_delay,
                timeout=self.config.timeout,
                max_retry_tokens=self.config.max_retry_tokens,
            )
            guard = CostAwareRetryGuard(self.config.max_retry_tokens)
            repair_usage: list[LLMUsage] = []

            async def _call(attempt: int) -> LLMResponse:
                nonlocal attempts
                attempts = attempt
                response = await agent_llm.chat(
                    messages,
                    model=model,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                )
                token_usage["input"] += response.usage.input_tokens
                token_usage["output"] += response.usage.output_tokens
                return response

            response = await async_retry(_call, config=retry_config, guard=guard)

            payload: Any = response.content
            if self.output_schema is not None:
                payload = await _parse_structured(
                    self.output_schema,
                    text=response.content,
                    llm=agent_llm,
                    usage_collector=repair_usage,
                )
            data = self._validate_output(payload)

            for usage in repair_usage:
                token_usage["input"] += usage.input_tokens
                token_usage["output"] += usage.output_tokens

            duration = time.perf_counter() - started
            usage_total = LLMUsage(
                input_tokens=token_usage["input"],
                output_tokens=token_usage["output"],
            )
            cost = compute_cost(usage_total).total_cost
            result = AgentResult(
                success=True,
                data=data,
                metadata={
                    "agent": self.config.name,
                    "version": self.config.version,
                    "model": model,
                    "degradation": level.value,
                    "attempts": attempts + 1,
                    "input_guard_hits": len(guard_hits),
                },
                warnings=list(guard_hits),
                duration=duration,
                token_usage=token_usage,
                cost=cost,
            )
            await self._track_success(
                session,
                usage=usage_total,
                model=model,
                task_id=task_id,
                attempt=attempts,
                user_id=user_id,
                datasource_id=datasource_id,
                duration=duration,
                key_source=key_source,
            )
            record_agent_invocation(
                agent=self.config.name, status="success", duration_seconds=duration
            )
            return result

        except Exception as exc:  # noqa: BLE001 - 对外统一返回失败结果
            duration = time.perf_counter() - started
            logger.opt(exception=exc).warning(
                "agent execution failed agent={} error={}",
                self.config.name,
                type(exc).__name__,
            )
            await self._track_failure(
                session,
                error=exc,
                model=model,
                task_id=task_id,
                attempt=attempts,
                user_id=user_id,
                datasource_id=datasource_id,
                duration=duration,
                key_source=key_source,
            )

            # ── BYOK：用户 Key 失效 → 幂等标记 invalid，抛可读错误（不回退服务端 Key） ──
            if (
                isinstance(exc, LLMAuthenticationError)
                and byok_key is not None
                and user_id is not None
            ):
                from app.services.credential_service import credential_service

                await credential_service.mark_invalid(user_id)
                record_agent_invocation(
                    agent=self.config.name, status="failed", duration_seconds=duration
                )
                raise LLMCredentialInvalidError() from exc

            record_agent_invocation(
                agent=self.config.name, status="failed", duration_seconds=duration
            )
            return AgentResult(
                success=False,
                metadata={
                    "agent": self.config.name,
                    "version": self.config.version,
                    "model": model,
                    "degradation": level.value,
                    "attempts": attempts + 1,
                    "input_guard_hits": len(guard_hits),
                },
                errors=[f"{type(exc).__name__}: {exc}"],
                warnings=list(guard_hits),
                duration=duration,
                token_usage=token_usage,
            )

    # -- 内部辅助 ---------------------------------------------------------
    async def _resolve_level(
        self, session: AsyncSession | None, user_id: uuid.UUID | None
    ) -> DegradationLevel:
        return await DegradationManager(session).get_level(user_id=user_id)

    async def _track_success(
        self,
        session: AsyncSession | None,
        *,
        usage: LLMUsage,
        model: str,
        task_id: uuid.UUID | str | None,
        attempt: int,
        user_id: uuid.UUID | None,
        datasource_id: uuid.UUID | None,
        duration: float,
        key_source: str = "server",
    ) -> None:
        if session is None or not settings.LLM_CALL_LOG_ENABLED:
            return
        synthetic = LLMResponse(
            content="",
            usage=usage,
            model=model,
            latency_ms=duration * 1000,
        )
        try:
            await CostTracker(session).track(
                response=synthetic,
                task_id=task_id,
                attempt=attempt,
                user_id=user_id,
                datasource_id=datasource_id,
                agent_name=self.config.name,
                agent_version=self.config.version,
                key_source=key_source,
            )
        except Exception as exc:  # noqa: BLE001 - 追踪失败不应影响业务结果
            logger.opt(exception=exc).error("cost tracking failed")

    async def _track_failure(
        self,
        session: AsyncSession | None,
        *,
        error: BaseException,
        model: str,
        task_id: uuid.UUID | str | None,
        attempt: int,
        user_id: uuid.UUID | None,
        datasource_id: uuid.UUID | None,
        duration: float,
        key_source: str = "server",
    ) -> None:
        if session is None or not settings.LLM_CALL_LOG_ENABLED:
            return
        try:
            await CostTracker(session).record_failure(
                error=error,
                model=model,
                task_id=task_id,
                attempt=attempt,
                user_id=user_id,
                datasource_id=datasource_id,
                agent_name=self.config.name,
                agent_version=self.config.version,
                duration_seconds=duration,
                key_source=key_source,
            )
        except Exception as exc:  # noqa: BLE001
            logger.opt(exception=exc).error("failure tracking failed")


async def _parse_structured(
    schema: type[BaseModel],
    *,
    text: str,
    llm: LLMClient,
    usage_collector: list[LLMUsage],
) -> BaseModel:
    """延迟导入避免模块循环（structured_output 依赖 llm，不依赖 base）。"""
    from app.agents.structured_output import parse_with_repair

    return await parse_with_repair(
        text=text,
        schema=schema,
        llm=llm,
        usage_collector=usage_collector,
    )


__all__ = [
    "AgentConfig",
    "AgentDegradedError",
    "AgentError",
    "AgentExecutionError",
    "AgentInputError",
    "AgentOutputError",
    "AgentResult",
    "AgentTimeoutError",
    "BaseAgent",
    "CleaningError",
    "EvaluationError",
    "ExtractionError",
    "InsightError",
    "ReportError",
]
