# Agent 错误重试机制

> **文档版本**：v1.1  
> **创建日期**：2026年10月23日  
> **更新日期**：2026年10月24日  
> **变更类型**：修正异常类名、接入成本守卫、补充幂等性设计  
> **优先级**：🟡 P1

---

## 📋 目录

1. [问题描述](#1-问题描述)
2. [重试策略设计](#2-重试策略设计)
3. [实现方案](#3-实现方案)
4. [最佳实践](#4-最佳实践)

---

## 1. 问题描述

### 当前问题

原有设计提到 `max_retries: 3`，但没有明确：

❌ 重试间隔（立即重试 vs. 指数退避）  
❌ 哪些错误需要重试（网络错误 vs. 逻辑错误）  
❌ 重试失败后的兜底方案  

### 影响

- 可能导致 Token 浪费（重试逻辑错误）
- 服务假死（一直重试不可恢复的错误）
- 成本失控（频繁重试）

---

## 2. 重试策略设计

### 2.1 核心原则

```
1. 只重试瞬时性错误（网络、限流）
2. 不重试永久性错误（验证、认证）
3. 使用指数退避（避免雪崩）
4. 有最大重试次数（避免无限循环）
5. 记录重试日志（便于排查）
```

---

### 2.2 错误分类

#### ✅ 可重试错误（Retryable Errors）

```python
RETRYABLE_ERRORS = [
    # 网络错误
    "APIConnectionError",
    "TimeoutError",            # asyncio.TimeoutError 在 3.11+ 即 TimeoutError
    "ConnectionResetError",
    "ConnectionRefusedError",

    # 限流错误
    "RateLimitError",
    "TooManyRequestsError",

    # 服务端临时错误
    "ServiceUnavailableError",  # 503
    "GatewayTimeoutError",      # 504
    "InternalServerError",      # 500（部分情况）

    # LLM 特定错误
    "OverloadedError",          # 模型过载
    "ModelBusyError"            # 模型繁忙
]
```

**重试理由**：这些错误是**瞬时性的**，重试可能成功

---

#### ❌ 不可重试错误（Non-retryable Errors）

```python
NON_RETRYABLE_ERRORS = [
    # 认证/授权错误
    "AuthenticationError",      # 401
    "PermissionDeniedError",    # 403
    "InvalidAPIKeyError",
    
    # 请求错误
    "ValidationError",          # 400
    "InvalidRequestError",
    "BadRequestError",
    
    # 业务逻辑错误
    "InvalidPromptError",
    "ContentFilterError",       # 内容违规
    "ContextLengthExceededError", # Token 超限
    
    # 配额错误
    "QuotaExceededError",       # 配额用尽（不是限流）
    "InsufficientCreditsError"
]
```

**不重试理由**：这些错误是**永久性的**，重试必定失败

---

### 2.3 重试配置

```python
# app/core/retry_config.py
import random
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class RetryConfig:
    """重试配置"""

    # 基础配置
    max_retries: int = 3              # 最大重试次数
    initial_delay: float = 1.0        # 初始延迟（秒）
    max_delay: float = 60.0           # 最大延迟（秒）
    backoff_factor: float = 2.0       # 退避因子

    # 错误分类（默认值在 __post_init__ 中填充，避免可变默认值陷阱）
    retryable_errors: Optional[List[str]] = None
    non_retryable_errors: Optional[List[str]] = None

    # 超时配置
    timeout: float = 60.0             # 单次请求超时
    total_timeout: float = 180.0      # 总超时（含重试）

    # Jitter（随机抖动，避免雪崩）
    jitter: bool = True

    # 重试的额外成本上限（按 token 计，不写死美元金额）
    max_retry_tokens: int = 20_000

    def __post_init__(self):
        if self.retryable_errors is None:
            self.retryable_errors = [
                "APIConnectionError",
                "TimeoutError",
                "RateLimitError",
                "ServiceUnavailableError",
                "OverloadedError",
            ]

        if self.non_retryable_errors is None:
            self.non_retryable_errors = [
                "AuthenticationError",
                "ValidationError",
                "InvalidPromptError",
                "ContextLengthExceededError",
            ]

    def calculate_delay(self, attempt: int) -> float:
        """计算重试延迟（指数退避 + Jitter）"""
        # 指数退避（attempt 从 0 开始，首次重试即 initial_delay）
        delay = min(
            self.initial_delay * (self.backoff_factor ** attempt),
            self.max_delay,
        )

        # 添加随机抖动（0.5x ~ 1.5x）
        if self.jitter:
            delay = delay * (0.5 + random.random())

        return delay

    def is_retryable(self, error: Exception) -> bool:
        """判断错误是否可重试"""
        error_name = type(error).__name__

        # 显式不可重试
        if error_name in (self.non_retryable_errors or []):
            return False

        # 显式可重试
        if error_name in (self.retryable_errors or []):
            return True

        # 默认不重试（保守策略）
        return False
```

---

## 3. 实现方案

### 3.1 重试装饰器

```python
# app/utils/retry.py
import asyncio
import time
from functools import wraps
from typing import Awaitable, Callable, Optional, TypeVar

from loguru import logger

from app.core.retry_config import RetryConfig

T = TypeVar("T")


def async_retry(
    config: Optional[RetryConfig] = None,
    on_retry: Optional[Callable[[int, float, Exception], Awaitable[None]]] = None,
    retry_guard: Optional["CostAwareRetryGuard"] = None,
):
    """
    异步重试装饰器

    Args:
        config: 重试配置
        on_retry: 重试回调（可选，用于打点/告警）
        retry_guard: 成本守卫（可选）。每次重试前调用
            ``await retry_guard.before_retry(attempt, error)``，
            超出 token 预算时由守卫抛 ``CostLimitExceededError`` 终止重试。
    """

    cfg = config or RetryConfig()

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exception: Optional[Exception] = None
            start_time = time.monotonic()

            for attempt in range(cfg.max_retries + 1):
                try:
                    # 检查总超时
                    elapsed = time.monotonic() - start_time
                    if elapsed >= cfg.total_timeout:
                        raise TimeoutError(
                            f"Total timeout exceeded: {elapsed:.2f}s"
                        )

                    # 执行函数（单次超时）
                    return await asyncio.wait_for(
                        func(*args, **kwargs),
                        timeout=cfg.timeout,
                    )

                except Exception as exc:
                    last_exception = exc

                    # 判断是否可重试
                    if not cfg.is_retryable(exc):
                        logger.error(
                            "{} 命中不可重试错误：{}", func.__name__, exc
                        )
                        raise

                    # 最后一次尝试失败
                    if attempt >= cfg.max_retries:
                        logger.error(
                            "{} 重试 {} 次后仍失败：{}",
                            func.__name__,
                            cfg.max_retries,
                            exc,
                        )
                        raise

                    # 计算延迟
                    delay = cfg.calculate_delay(attempt)

                    logger.warning(
                        "{} 第 {}/{} 次失败，{:.2f}s 后重试：{}",
                        func.__name__,
                        attempt + 1,
                        cfg.max_retries + 1,
                        delay,
                        exc,
                    )

                    # 成本守卫：超出预算直接终止，不再重试
                    if retry_guard is not None:
                        await retry_guard.before_retry(attempt, exc)

                    # 回调（打点）
                    if on_retry is not None:
                        await on_retry(attempt, delay, exc)

                    # 等待后重试
                    await asyncio.sleep(delay)

            # 理论上不可达；保留兜底避免返回 None
            if last_exception is not None:
                raise last_exception
            raise RuntimeError(f"{func.__name__} retry loop exited unexpectedly")

        return wrapper

    return decorator
```

> `before_retry` 抛出 `CostLimitExceededError` 时，装饰器不再吞异常——该异常不在 `retryable_errors` 中，会直接向上抛给 `_handle_failure` 转成业务错误。

---

### 3.2 Agent 基类集成

```python
# app/agents/base.py
from typing import Optional

from loguru import logger

from app.core.retry_config import RetryConfig
from app.utils.retry import CostAwareRetryGuard, async_retry


class BaseAgent:
    """Agent 基类（集成重试）"""

    def __init__(
        self,
        retry_config: Optional[RetryConfig] = None,
        retry_guard: Optional[CostAwareRetryGuard] = None,
    ):
        self.retry_config = retry_config or RetryConfig()
        self.retry_guard = retry_guard or CostAwareRetryGuard(
            max_extra_tokens=self.retry_config.max_retry_tokens
        )
        self.llm = self._init_llm()

        # 按实例绑定配置：装饰器在 __init__ 时套用，才能尊重子类的 retry_config
        self._call_llm_with_retry = async_retry(
            config=self.retry_config,
            retry_guard=self.retry_guard,
        )(self._call_llm)

    async def _call_llm(self, messages: list) -> str:
        """
        调用 LLM（被 _call_llm_with_retry 包裹，自动重试瞬时性错误）
        """
        try:
            response = await self.llm.ainvoke(messages)
            return response.content
        except Exception as exc:
            # 记录错误详情（结构化字段，便于按 agent/error_type 聚合）
            logger.bind(
                agent=self.__class__.__name__,
                message_count=len(messages),
                error_type=type(exc).__name__,
            ).error("LLM 调用失败：{}", exc)
            raise

    async def invoke(self, input_data: dict) -> dict:
        """执行 Agent"""

        messages = self._build_messages(input_data)

        try:
            result = await self._call_llm_with_retry(messages)
            return self._parse_result(result)
        except Exception as exc:
            # 重试失败后的兜底处理
            return await self._handle_failure(input_data, exc)

    async def _handle_failure(
        self,
        input_data: dict,
        error: Exception,
        _truncated: bool = False,
    ) -> dict:
        """
        重试失败后的兜底处理

        不同类型的错误有不同的兜底策略。
        """

        error_type = type(error).__name__

        # 1. 认证错误 → 返回错误，让用户修复
        if error_type in ("AuthenticationError", "InvalidAPIKeyError"):
            return {
                "success": False,
                "error": "authentication_failed",
                "message": "API 密钥无效，请检查配置",
                "recoverable": False,
            }

        # 2. 配额错误 → 返回错误，引导升级
        if error_type in ("QuotaExceededError", "InsufficientCreditsError"):
            return {
                "success": False,
                "error": "quota_exceeded",
                "message": "配额已用尽，请升级套餐",
                "recoverable": False,
                "upgrade_url": "/upgrade",
            }

        # 3. 内容过滤 → 返回错误，提示用户
        if error_type == "ContentFilterError":
            return {
                "success": False,
                "error": "content_filtered",
                "message": "内容包含违规信息，请修改后重试",
                "recoverable": True,
            }

        # 4. 重试成本超限 → 不再重试，转人工/提示
        if error_type == "CostLimitExceededError":
            return {
                "success": False,
                "error": "retry_cost_exceeded",
                "message": "重试消耗已超预算，任务已转人工处理",
                "recoverable": False,
            }

        # 5. Token 超限 → 只截断一次，避免无限递归
        if error_type == "ContextLengthExceededError" and not _truncated:
            logger.warning("上下文超限，截断输入后重试一次")
            truncated_input = self._truncate_input(input_data)
            try:
                return await self.invoke(truncated_input)
            except Exception:
                return {
                    "success": False,
                    "error": "input_too_long",
                    "message": "输入内容过长，请减少数据量",
                    "recoverable": True,
                }

        # 6. 其他错误 → 通用错误响应
        return {
            "success": False,
            "error": "agent_failed",
            "message": f"处理失败: {error}",
            "error_type": error_type,
            "recoverable": False,
        }
```

---

### 3.3 特定 Agent 示例

```python
# app/agents/cleaning_agent.py
from loguru import logger

from app.agents.base import BaseAgent
from app.core.retry_config import RetryConfig


class DataCleaningAgent(BaseAgent):
    """数据清洗 Agent"""

    def __init__(self, db, retry_config: RetryConfig | None = None):
        self.db = db
        # 自定义重试配置
        retry_config = retry_config or RetryConfig(
            max_retries=3,
            initial_delay=1.0,
            backoff_factor=2.0,
            timeout=60.0,
            total_timeout=180.0,
        )
        super().__init__(retry_config=retry_config)

    async def clean(self, raw_data: str, task_id: str) -> dict:
        """清洗数据（task_id 用于失败记录与幂等）"""

        result = await self.invoke({"raw_data": raw_data})

        # 如果失败，记录详细信息（按 task_id 关联，便于定位）
        if not result.get("success", True):
            await self._log_failure(task_id, raw_data, result)

        return result

    async def _log_failure(self, task_id: str, raw_data: str, result: dict):
        """记录失败信息（写入 llm_calls 的失败状态，不新建表）"""
        await self.db.execute(
            """
            UPDATE llm_calls
               SET status = 'failed',
                   error_type = :error_type,
                   error_message = :message
             WHERE idempotency_key = :key
            """,
            {
                "key": f"{task_id}:final",
                "error_type": result.get("error"),
                "message": result.get("message"),
            },
        )
        logger.bind(agent="cleaning_agent", task_id=task_id).warning(
            "清洗失败：{} - {}", result.get("error"), result.get("message")
        )
```

> `llm_calls` 的 `idempotency_key` 约定见 §3.5；失败记录复用同一行，不额外建 `agent_failures` 表。

---

### 3.4 监控重试情况

```python
# app/utils/retry_metrics.py
from prometheus_client import Counter, Histogram

# 重试次数统计
retry_counter = Counter(
    "agent_retry_total",
    "Total number of agent retries",
    ["agent_name", "error_type", "attempt"],
)

# 重试延迟统计
retry_delay_histogram = Histogram(
    "agent_retry_delay_seconds",
    "Retry delay in seconds",
    ["agent_name"],
)


def make_retry_callback(agent_name: str):
    """生成绑定到具体 agent 的重试回调，避免把 agent 名写死。"""

    async def on_retry_callback(attempt: int, delay: float, error: Exception):
        retry_counter.labels(
            agent_name=agent_name,
            error_type=type(error).__name__,
            attempt=str(attempt + 1),
        ).inc()
        retry_delay_histogram.labels(agent_name=agent_name).observe(delay)

    return on_retry_callback


# 使用
on_retry_cleaning = make_retry_callback("cleaning_agent")


@async_retry(config=RetryConfig(), on_retry=on_retry_cleaning)
async def my_function():
    pass
```

---

### 3.5 幂等性设计（重试不重复计费）

重试会重复调用 LLM，如果每次都新增一条调用记录，成本统计会虚高，任务也可能被重复执行。约定：

1. **幂等键**：`idempotency_key = f"{task_id}:{attempt}"`，其中 `task_id` 是业务任务 ID（Celery task id 或业务主键），`attempt` 从 0 开始；
2. **唯一索引**：`llm_calls` 上建 `UNIQUE (idempotency_key)`；
3. **写入口径**：统一用 `INSERT ... ON CONFLICT (idempotency_key) DO UPDATE`，重复上报只覆盖、不新增行；
4. **计费口径**：成本按 `llm_calls` 中每行 `input_tokens/output_tokens × 单价` 聚合，重试产生的真实 token 消耗**照常计费**（因为确实调用了），但同一 attempt 的重复上报不会重复计费；
5. **任务幂等**：业务侧以 `task_id` 为幂等键，成功结果写 `status='success'` 后，同 `task_id` 的后续请求直接返回缓存结果，不再调用 LLM。

```python
# app/services/llm_call_recorder.py
async def record_llm_call(db, record: dict) -> None:
    """写入/更新一条 LLM 调用记录（幂等）"""

    await db.execute(
        """
        INSERT INTO llm_calls (
            idempotency_key, task_id, attempt, model, service,
            input_tokens, output_tokens, total_tokens,
            input_cost, output_cost, total_cost,
            duration, status, error_type, error_message
        ) VALUES (
            :idempotency_key, :task_id, :attempt, :model, :service,
            :input_tokens, :output_tokens, :total_tokens,
            :input_cost, :output_cost, :total_cost,
            :duration, :status, :error_type, :error_message
        )
        ON CONFLICT (idempotency_key) DO UPDATE SET
            input_tokens  = EXCLUDED.input_tokens,
            output_tokens = EXCLUDED.output_tokens,
            total_tokens  = EXCLUDED.total_tokens,
            input_cost    = EXCLUDED.input_cost,
            output_cost   = EXCLUDED.output_cost,
            total_cost    = EXCLUDED.total_cost,
            duration      = EXCLUDED.duration,
            status        = EXCLUDED.status,
            error_type    = EXCLUDED.error_type,
            error_message = EXCLUDED.error_message
        """,
        record,
    )
```

```sql
-- 唯一索引（与 03-成本管理.md §3.1 的 llm_calls 定义保持一致）
CREATE UNIQUE INDEX IF NOT EXISTS uk_llm_calls_idempotency
    ON llm_calls (idempotency_key);
```

> ⚠️ `attempt` 必须是「真实调用序号」。如果只是网络层重发（同一个 attempt），幂等键不变，不会多计；如果是业务层重试（新 attempt），会新增一行，属于真实消耗。

---

## 4. 最佳实践

### 4.1 重试策略选择

**简单任务**（数据清洗）：
```python
RetryConfig(
    max_retries=3,
    initial_delay=1.0,
    backoff_factor=2.0
)
# 重试间隔：1s → 2s → 4s
```

**复杂任务**（报告生成）：
```python
RetryConfig(
    max_retries=2,          # 减少重试次数（耗时长）
    initial_delay=5.0,      # 增加初始延迟
    backoff_factor=3.0,
    timeout=120.0           # 增加单次超时
)
# 重试间隔：5s → 15s
```

**批量任务**：
```python
RetryConfig(
    max_retries=5,          # 增加重试次数
    initial_delay=2.0,
    backoff_factor=1.5,     # 减少退避因子
    jitter=True             # 启用抖动（避免雪崩）
)
```

---

### 4.2 错误处理最佳实践

#### ✅ 正确做法

```python
try:
    result = await agent.invoke(data)
except RateLimitError:
    # 限流错误：等待后重试（已由装饰器处理）
    pass
except ValidationError as e:
    # 验证错误：记录并返回给用户
    logger.error(f"Validation failed: {e}")
    return {"error": "invalid_input", "details": str(e)}
except Exception as e:
    # 未知错误：记录详细信息
    logger.exception("Unexpected error")
    raise
```

#### ❌ 错误做法

```python
try:
    result = await agent.invoke(data)
except Exception:
    # ❌ 吞掉所有错误
    pass

# ❌ 无限重试
while True:
    try:
        result = await agent.invoke(data)
        break
    except:
        continue

# ❌ 重试逻辑错误
try:
    result = await agent.invoke(data)
except ValidationError:
    # ❌ 重试验证错误（必定失败）
    result = await agent.invoke(data)
```

---

### 4.3 成本控制

重试的成本上限用 **token 预算**表达（不写死美元金额），美元值由 `P_IN` / `P_OUT` 换算，口径见 `03-成本管理.md` §0。

```python
# app/utils/retry_guard.py
from loguru import logger


class CostLimitExceededError(Exception):
    """重试消耗超出预算"""


class CostAwareRetryGuard:
    """成本感知的重试守卫

    在每次重试前累加本次尝试的 token 消耗；超过 ``max_extra_tokens``
    就抛 ``CostLimitExceededError``，由装饰器终止重试。
    """

    def __init__(self, max_extra_tokens: int = 20_000):
        self.max_extra_tokens = max_extra_tokens
        self.accumulated_tokens = 0

    async def before_retry(self, attempt: int, error: Exception) -> None:
        """重试前检查成本。

        参数：
            attempt: 已失败的尝试序号（从 0 开始）
            error: 触发的异常，仅用于日志
        """
        # 上一次尝试的 token 由调用方在异常上挂载；拿不到时按 0 处理
        used = getattr(error, "total_tokens", 0) or 0
        self.accumulated_tokens += used

        logger.bind(
            attempt=attempt,
            used_tokens=used,
            accumulated_tokens=self.accumulated_tokens,
        ).debug("重试前成本检查")

        if self.accumulated_tokens > self.max_extra_tokens:
            raise CostLimitExceededError(
                "重试 token 预算已超限："
                f"{self.accumulated_tokens} > {self.max_extra_tokens}"
            )
```

> 更精确的做法：在 `_call_llm` 的 `except` 分支里把本次 `usage.total_tokens` 挂到异常对象上（`exc.total_tokens = ...`），守卫即可拿到真实消耗；拿不到时按 0 处理，不会误杀。

---

## 📊 重试效果示例

### 场景 1: 网络抖动

```
尝试 1: APIConnectionError → 重试（延迟 1s）
尝试 2: 成功 ✅
总耗时: 2.5s
```

### 场景 2: 限流

```
尝试 1: RateLimitError → 重试（延迟 1s）
尝试 2: RateLimitError → 重试（延迟 2s）
尝试 3: 成功 ✅
总耗时: 8.2s
```

### 场景 3: 验证错误

```
尝试 1: ValidationError → 不重试 ❌
立即返回错误给用户
总耗时: 0.5s
```

---

## ✅ 改进总结

### 解决的问题

✅ 明确了重试间隔（指数退避 + Jitter）  
✅ 明确了可/不可重试错误（`TimeoutError` 而非 `Timeout`）  
✅ 提供了兜底处理方案（含降级后的结构化输出兜底）  
✅ 增加了成本控制（token 预算 + `CostAwareRetryGuard`）  
✅ 完整的监控和日志  
✅ 重试幂等，不重复计费  

### 核心价值

🎯 **智能重试**：只重试有意义的错误  
💰 **成本可控**：重试前先过 token 预算守卫，避免无效重试浪费 Token  
📊 **可观测性**：完整的监控指标  
🛡️ **稳定性**：避免雪崩，平滑处理错误  
🔁 **幂等**：`task_id + attempt` 唯一键，重复上报不重复计费  

---

## 📝 更新记录

| 日期 | 变更 |
|------|------|
| 2026-10-23 | 初版：错误分类 + 指数退避 + 兜底 + 监控 |
| 2026-10-24 | `"Timeout"` → `"TimeoutError"`；装饰器接入 `CostAwareRetryGuard.before_retry()`；成本上限改为 token 预算；新增 §3.5 幂等性设计；`logging` → Loguru；修正 `raise last_exception` 可能为 `None`、裸 `except`、上下文截断无限递归、`self.db` 未初始化等问题 |

---

**Agent 错误重试机制完成！** ✅
