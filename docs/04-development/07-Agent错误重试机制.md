# Agent 错误重试机制

> **文档版本**：v1.0  
> **创建日期**：2026年10月23日  
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
    "Timeout",
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
from dataclasses import dataclass
from typing import List, Tuple

@dataclass
class RetryConfig:
    """重试配置"""
    
    # 基础配置
    max_retries: int = 3              # 最大重试次数
    initial_delay: float = 1.0        # 初始延迟（秒）
    max_delay: float = 60.0           # 最大延迟（秒）
    backoff_factor: float = 2.0       # 退避因子
    
    # 错误分类
    retryable_errors: List[str] = None
    non_retryable_errors: List[str] = None
    
    # 超时配置
    timeout: float = 60.0             # 单次请求超时
    total_timeout: float = 180.0      # 总超时（含重试）
    
    # Jitter（随机抖动，避免雪崩）
    jitter: bool = True
    
    def __post_init__(self):
        if self.retryable_errors is None:
            self.retryable_errors = [
                "APIConnectionError",
                "Timeout",
                "RateLimitError",
                "ServiceUnavailableError",
                "OverloadedError"
            ]
        
        if self.non_retryable_errors is None:
            self.non_retryable_errors = [
                "AuthenticationError",
                "ValidationError",
                "InvalidPromptError",
                "ContextLengthExceededError"
            ]
    
    def calculate_delay(self, attempt: int) -> float:
        """计算重试延迟（指数退避 + Jitter）"""
        import random
        
        # 指数退避
        delay = min(
            self.initial_delay * (self.backoff_factor ** attempt),
            self.max_delay
        )
        
        # 添加随机抖动（0.5x ~ 1.5x）
        if self.jitter:
            delay = delay * (0.5 + random.random())
        
        return delay
    
    def is_retryable(self, error: Exception) -> bool:
        """判断错误是否可重试"""
        error_name = type(error).__name__
        
        # 显式不可重试
        if error_name in self.non_retryable_errors:
            return False
        
        # 显式可重试
        if error_name in self.retryable_errors:
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
import logging
import time
from functools import wraps
from typing import Callable, TypeVar, Any

logger = logging.getLogger(__name__)

T = TypeVar('T')

def async_retry(
    config: RetryConfig = None,
    on_retry: Callable = None
):
    """
    异步重试装饰器
    
    Args:
        config: 重试配置
        on_retry: 重试回调函数（可选）
    """
    
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exception = None
            start_time = time.time()
            
            for attempt in range(config.max_retries + 1):
                try:
                    # 检查总超时
                    elapsed = time.time() - start_time
                    if elapsed >= config.total_timeout:
                        raise TimeoutError(
                            f"Total timeout exceeded: {elapsed:.2f}s"
                        )
                    
                    # 执行函数
                    return await asyncio.wait_for(
                        func(*args, **kwargs),
                        timeout=config.timeout
                    )
                
                except Exception as e:
                    last_exception = e
                    
                    # 判断是否可重试
                    if not config.is_retryable(e):
                        logger.error(
                            f"{func.__name__} failed with non-retryable error: {e}"
                        )
                        raise
                    
                    # 最后一次尝试失败
                    if attempt >= config.max_retries:
                        logger.error(
                            f"{func.__name__} failed after {config.max_retries} retries"
                        )
                        raise
                    
                    # 计算延迟
                    delay = config.calculate_delay(attempt)
                    
                    logger.warning(
                        f"{func.__name__} failed (attempt {attempt + 1}/{config.max_retries + 1}), "
                        f"retrying in {delay:.2f}s: {e}"
                    )
                    
                    # 回调
                    if on_retry:
                        await on_retry(attempt, delay, e)
                    
                    # 等待后重试
                    await asyncio.sleep(delay)
            
            # 不应该到达这里
            raise last_exception
        
        return wrapper
    return decorator
```

---

### 3.2 Agent 基类集成

```python
# app/agents/base.py
from app.utils.retry import async_retry
from app.core.retry_config import RetryConfig

class BaseAgent:
    """Agent 基类（集成重试）"""
    
    def __init__(self, retry_config: RetryConfig = None):
        self.retry_config = retry_config or RetryConfig()
        self.llm = self._init_llm()
    
    @async_retry(config=RetryConfig(max_retries=3))
    async def _call_llm(self, messages: list) -> str:
        """
        调用 LLM（带重试）
        
        这个方法会自动重试瞬时性错误
        """
        try:
            response = await self.llm.ainvoke(messages)
            return response.content
        
        except Exception as e:
            # 记录错误详情
            logger.error(
                f"LLM call failed: {e}",
                extra={
                    "agent": self.__class__.__name__,
                    "message_count": len(messages),
                    "error_type": type(e).__name__
                }
            )
            raise
    
    async def invoke(self, input_data: dict) -> dict:
        """执行 Agent"""
        
        # 构建消息
        messages = self._build_messages(input_data)
        
        # 调用 LLM（自动重试）
        try:
            result = await self._call_llm(messages)
            return self._parse_result(result)
        
        except Exception as e:
            # 重试失败后的兜底处理
            return await self._handle_failure(input_data, e)
    
    async def _handle_failure(
        self,
        input_data: dict,
        error: Exception
    ) -> dict:
        """
        重试失败后的兜底处理
        
        不同类型的错误有不同的兜底策略
        """
        
        error_type = type(error).__name__
        
        # 1. 认证错误 → 返回错误，让用户修复
        if error_type in ["AuthenticationError", "InvalidAPIKeyError"]:
            return {
                "success": False,
                "error": "authentication_failed",
                "message": "API 密钥无效，请检查配置",
                "recoverable": False
            }
        
        # 2. 配额错误 → 返回错误，引导升级
        if error_type in ["QuotaExceededError", "InsufficientCreditsError"]:
            return {
                "success": False,
                "error": "quota_exceeded",
                "message": "配额已用尽，请升级套餐",
                "recoverable": False,
                "upgrade_url": "/upgrade"
            }
        
        # 3. 内容过滤 → 返回错误，提示用户
        if error_type == "ContentFilterError":
            return {
                "success": False,
                "error": "content_filtered",
                "message": "内容包含违规信息，请修改后重试",
                "recoverable": True
            }
        
        # 4. Token 超限 → 尝试截断输入
        if error_type == "ContextLengthExceededError":
            logger.warning("Context length exceeded, trying with truncated input")
            truncated_input = self._truncate_input(input_data)
            try:
                return await self.invoke(truncated_input)
            except:
                return {
                    "success": False,
                    "error": "input_too_long",
                    "message": "输入内容过长，请减少数据量",
                    "recoverable": True
                }
        
        # 5. 其他错误 → 通用错误响应
        return {
            "success": False,
            "error": "agent_failed",
            "message": f"处理失败: {str(error)}",
            "error_type": error_type,
            "recoverable": False
        }
```

---

### 3.3 特定 Agent 示例

```python
# app/agents/cleaning_agent.py
from app.agents.base import BaseAgent
from app.core.retry_config import RetryConfig

class DataCleaningAgent(BaseAgent):
    """数据清洗 Agent"""
    
    def __init__(self):
        # 自定义重试配置
        retry_config = RetryConfig(
            max_retries=3,
            initial_delay=1.0,
            backoff_factor=2.0,
            timeout=60.0,
            total_timeout=180.0
        )
        super().__init__(retry_config=retry_config)
    
    async def clean(self, raw_data: str) -> dict:
        """清洗数据"""
        
        result = await self.invoke({
            "raw_data": raw_data
        })
        
        # 如果失败，记录详细信息
        if not result.get("success", True):
            await self._log_failure(raw_data, result)
        
        return result
    
    async def _log_failure(self, raw_data: str, result: dict):
        """记录失败信息"""
        await self.db.execute(
            """
            INSERT INTO agent_failures (
                agent_name, input_data, error_type, error_message
            ) VALUES (
                :agent, :input, :error_type, :message
            )
            """,
            {
                "agent": "cleaning_agent",
                "input": raw_data[:1000],  # 只存前 1000 字符
                "error_type": result.get("error"),
                "message": result.get("message")
            }
        )
```

---

### 3.4 监控重试情况

```python
# app/utils/retry_metrics.py
from prometheus_client import Counter, Histogram

# 重试次数统计
retry_counter = Counter(
    'agent_retry_total',
    'Total number of agent retries',
    ['agent_name', 'error_type', 'attempt']
)

# 重试延迟统计
retry_delay_histogram = Histogram(
    'agent_retry_delay_seconds',
    'Retry delay in seconds',
    ['agent_name']
)

# 在重试回调中记录指标
async def on_retry_callback(attempt: int, delay: float, error: Exception):
    """重试回调（记录监控指标）"""
    
    retry_counter.labels(
        agent_name="cleaning_agent",
        error_type=type(error).__name__,
        attempt=str(attempt + 1)
    ).inc()
    
    retry_delay_histogram.labels(
        agent_name="cleaning_agent"
    ).observe(delay)

# 使用
@async_retry(
    config=RetryConfig(),
    on_retry=on_retry_callback
)
async def my_function():
    pass
```

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

```python
# 限制重试导致的成本
class CostAwareRetryConfig(RetryConfig):
    """成本感知的重试配置"""
    
    def __init__(self, max_retry_cost: float = 0.01):
        super().__init__()
        self.max_retry_cost = max_retry_cost  # 最大重试成本
        self.accumulated_cost = 0.0
    
    async def before_retry(self, attempt: int, estimated_cost: float):
        """重试前检查成本"""
        self.accumulated_cost += estimated_cost
        
        if self.accumulated_cost > self.max_retry_cost:
            raise CostLimitExceededError(
                f"Retry cost limit exceeded: ${self.accumulated_cost:.4f}"
            )
```

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
✅ 明确了可/不可重试错误  
✅ 提供了兜底处理方案  
✅ 增加了成本控制  
✅ 完整的监控和日志  

### 核心价值

🎯 **智能重试**：只重试有意义的错误  
💰 **成本可控**：避免无效重试浪费 Token  
📊 **可观测性**：完整的监控指标  
🛡️ **稳定性**：避免雪崩，平滑处理错误  

---

**Agent 错误重试机制完成！** ✅
