# Prompt 版本管理方案

> **文档版本**：v1.1  
> **创建日期**：2026年10月23日  
> **变更类型**：补充完善

---

## 📋 目录

1. [问题描述](#1-问题描述)
2. [解决方案](#2-解决方案)
3. [数据库设计](#3-数据库设计)
4. [版本管理流程](#4-版本管理流程)
5. [A/B 测试](#5-ab-测试)
6. [版本回滚](#6-版本回滚)
7. [实现代码](#7-实现代码)

---

## 1. 问题描述

### 当前问题

原有 Prompt 工程规范提到了版本管理（version.txt），但缺少：

❌ 多版本并存机制（如何 A/B 测试）  
❌ 版本回滚流程  
❌ 版本与数据库记录的关联方式  
❌ 性能指标追踪  

### 影响

- Prompt 优化后无法追溯历史效果
- A/B 测试难以实施
- 出现问题时无法快速回滚
- 无法基于数据驱动优化 Prompt

---

## 2. 解决方案

### 核心设计

```
1. 数据库存储 Prompt 版本
2. 每次 Agent 调用记录使用的版本
3. 支持多版本并存（A/B 测试）
4. 自动收集性能指标
5. 一键回滚到历史版本
```

### 单一真相源（必须遵守）

`01-Prompt工程规范.md` 说 Prompt 存在 `prompts/**/*.txt` 文件里，本方案说存在数据库里 —— 两套载体必须定主从，否则改一处、跑一处，线上行为不可解释。

| 载体 | 定位 | 说明 |
|------|------|------|
| 数据库 `prompt_versions` 表 | **唯一真相源（Source of Truth）** | 生产运行时只从库读取；激活 / A/B / 回滚全部以库为准 |
| `backend/app/prompts/**/*.txt`（`system.txt` / `user_template.txt` / `examples.json` / `version.txt`） | 导出物 / 备份 / Code Review 产物 | 由 `export_to_files()` 从库导出，便于 Git diff 与评审 |

**同步规则**：

1. 任何 Prompt 改动 = ① 建 `draft` 版本入库 → ② `export_to_files()` 落盘 → ③ Git 提交（顺序不可颠倒）；
2. **禁止只改文件不改库**：下次 `export_to_files()` 会把文件覆盖回库里的旧内容；
3. 服务启动时若库中某 Agent 一条版本都没有，执行一次 `import_from_files()` 作为 bootstrap；
4. 文件与库不一致时以**库**为准，并打印告警（Loguru `WARNING`）＋ Prometheus 计数 `prompt_file_db_mismatch_total`；
5. 回滚只改库，再重新导出文件，不回滚 Git 历史（Git 侧用 `git revert` 保留可追溯性，见 `01-Prompt工程规范.md` 4.3 节）。

---

## 3. 数据库设计

> 本节给出 `prompt_versions`、`prompt_usage_logs`、`version_rollback_logs` 三张表的建表 SQL。
> **三张表已在 `docs/03-architecture/03-数据库设计.md` 登记**，本文件与之一致；若两处不一致，以 `03-数据库设计.md` 为准并回来同步修正本节。
> 数据库连接口径：库 / 用户 `aiinsight`，密码 `dev_password`（见 `docs/03-architecture/03-数据库设计.md` 与 `backend/.env.example`）。

### 3.1 Prompt 版本表（prompt_versions）

```sql
CREATE TABLE prompt_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 基础信息
    agent_name VARCHAR(100) NOT NULL,  -- cleaning_agent, evaluation_agent
    version VARCHAR(50) NOT NULL,      -- v1.0.0, v1.1.0
    
    -- Prompt 内容
    system_prompt TEXT NOT NULL,
    user_template TEXT,
    examples JSONB,                     -- Few-shot 示例
    
    -- 状态
    status VARCHAR(50) DEFAULT 'draft', -- draft/testing/active/deprecated
    is_default BOOLEAN DEFAULT FALSE,   -- 是否为默认版本
    
    -- 性能指标
    performance_metrics JSONB DEFAULT '{}',
    -- {
    --   "accuracy": 0.95,
    --   "avg_cost": 0.003,
    --   "avg_duration": 1.2,
    --   "total_uses": 1000,
    --   "error_rate": 0.02
    -- }
    
    -- A/B 测试配置
    ab_test_config JSONB DEFAULT '{}',
    -- {
    --   "enabled": true,
    --   "traffic_percentage": 0.1,  -- 10% 流量
    --   "start_date": "2026-10-23",
    --   "end_date": "2026-10-30"
    -- }
    
    -- 元数据
    created_by VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    activated_at TIMESTAMP,
    deprecated_at TIMESTAMP,
    
    -- 备注
    description TEXT,
    changelog TEXT,
    
    UNIQUE(agent_name, version)
);

-- 索引
CREATE INDEX idx_prompt_versions_agent ON prompt_versions(agent_name, status);
CREATE INDEX idx_prompt_versions_default ON prompt_versions(agent_name, is_default) 
    WHERE is_default = TRUE;
```

---

### 3.2 Prompt 使用记录表（prompt_usage_logs）

```sql
CREATE TABLE prompt_usage_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 关联
    prompt_version_id UUID REFERENCES prompt_versions(id),
    agent_name VARCHAR(100) NOT NULL,
    version VARCHAR(50) NOT NULL,
    
    -- 使用信息
    datasource_id UUID,
    user_id UUID,
    
    -- 性能数据
    duration FLOAT,              -- 执行时长（秒）
    token_usage JSONB,          -- {input: 100, output: 50}
    cost FLOAT,                 -- 成本（美元，按实际模型单价重算，不写死单价）
    
    -- 质量数据
    success BOOLEAN,
    error_message TEXT,
    quality_score FLOAT,        -- 输出质量评分（0-100）
    
    -- 时间戳
    created_at TIMESTAMP DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_prompt_usage_agent_version 
    ON prompt_usage_logs(agent_name, version, created_at);
CREATE INDEX idx_prompt_usage_prompt_id 
    ON prompt_usage_logs(prompt_version_id, created_at);
```

> **分区口径（MVP：普通表，不分区）**
>
> 与 `docs/04-development/11-数据库分区策略调整.md` 的「MVP 移除分区」结论保持一致，本表 MVP 阶段为**普通表**。
> 后续数据量增长再改为 `PARTITION BY RANGE (created_at)`（按月），但**不能只手工预建 2 个月分区**——写满后写入会直接失败。必须配套自动建分区机制：
>
> 1. Celery 每日凌晨任务 `ensure_next_month_partitions()`，始终保证「本月 + 下月 + 下下月」3 个分区存在；
> 2. 建分区用 `CREATE TABLE IF NOT EXISTS prompt_usage_logs_YYYY_MM PARTITION OF prompt_usage_logs FOR VALUES FROM (...) TO (...)`，幂等可重复执行；
> 3. Prometheus 暴露 `prompt_usage_partition_count`，< 3 时告警；
> 4. 转分区时主键须改为 `PRIMARY KEY (id, created_at)`（PG 要求唯一约束包含全部分区键），并重建索引。
>
> 具体分区时间点：待确认（确认方式：按 `prompt_usage_logs` 实际行数与查询 P95 压测后再定，参考阈值单表 > 1000 万行）。

---

### 3.3 版本回滚日志表（version_rollback_logs）

> 第 6 节回滚逻辑会写入本表，此前全文与数据库设计都**没有这张表**，此处补齐；**已在 `03-数据库设计.md` 登记**。

```sql
CREATE TABLE version_rollback_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    agent_name VARCHAR(100) NOT NULL,
    
    -- 回滚前正在生效的版本（必须先读出来再激活目标版本，见 6.1）
    from_version VARCHAR(50) NOT NULL,
    -- 回滚目标版本
    to_version VARCHAR(50) NOT NULL,
    
    -- 触发方式与原因
    trigger_type VARCHAR(20) DEFAULT 'manual' CHECK (
        trigger_type IN ('manual', 'auto')
    ),
    reason TEXT,
    -- 自动回滚时的错误率快照（0-1）
    error_rate FLOAT,
    
    created_by VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    
    -- 回滚源与目标不能是同一个版本，从数据库层拦住 6.1 曾出现的日志失真问题
    CHECK (from_version <> to_version)
);

CREATE INDEX idx_rollback_agent_created 
    ON version_rollback_logs(agent_name, created_at DESC);
```

---

## 4. 版本管理流程

### 4.1 创建新版本

```python
# app/services/prompt_version_service.py
# 伪代码：以下方法需在 PromptVersionService 中实现，本文档只给出关键实现
#   _log_usage / get_default_version / get_ab_test_version / get_version / list_versions /
#   get_previous_stable_version / send_alert / export_to_files / import_from_files
from pathlib import Path
import uuid
from datetime import datetime

class PromptVersionService:
    """Prompt 版本管理服务"""
    
    async def create_version(
        self,
        agent_name: str,
        version: str,
        system_prompt: str,
        user_template: str = None,
        examples: dict = None,
        description: str = None,
        created_by: str = None
    ) -> dict:
        """创建新版本"""
        
        # 1. 检查版本号是否已存在
        existing = await self.db.fetch_one(
            "SELECT id FROM prompt_versions WHERE agent_name = :agent AND version = :ver",
            {"agent": agent_name, "ver": version}
        )
        
        if existing:
            raise ValueError(f"Version {version} already exists for {agent_name}")
        
        # 2. 插入数据库
        #    ⚠️ asyncpg 的 execute() 只返回状态串（如 "INSERT 0 1"），拿不到 RETURNING 的值；
        #       要取回自增/默认生成的 id，必须用 fetch_val()。
        version_id = await self.db.fetch_val(
            """
            INSERT INTO prompt_versions (
                agent_name, version, system_prompt, user_template, examples,
                status, description, created_by
            ) VALUES (
                :agent_name, :version, :system_prompt, :user_template, :examples,
                'draft', :description, :created_by
            ) RETURNING id
            """,
            {
                "agent_name": agent_name,
                "version": version,
                "system_prompt": system_prompt,
                "user_template": user_template,
                "examples": examples,
                "description": description,
                "created_by": created_by
            }
        )
        
        # 3. 落盘导出（库是唯一真相源，文件是导出物，见第 2 节同步规则）
        await self.export_to_files(agent_name, version)
        
        return {
            "id": version_id,
            "agent_name": agent_name,
            "version": version,
            "status": "draft"
        }
```

---

### 4.2 激活版本

```python
async def activate_version(
    self,
    agent_name: str,
    version: str
) -> dict:
    """激活版本（设为默认）"""
    
    async with self.db.transaction():
        # 1. 取消当前默认版本
        await self.db.execute(
            """
            UPDATE prompt_versions
            SET is_default = FALSE
            WHERE agent_name = :agent AND is_default = TRUE
            """,
            {"agent": agent_name}
        )
        
        # 2. 激活新版本
        await self.db.execute(
            """
            UPDATE prompt_versions
            SET is_default = TRUE,
                status = 'active',
                activated_at = NOW()
            WHERE agent_name = :agent AND version = :version
            """,
            {"agent": agent_name, "version": version}
        )
    
    return {"agent_name": agent_name, "version": version, "status": "active"}
```

---

### 4.3 弃用版本

```python
async def deprecate_version(
    self,
    agent_name: str,
    version: str
) -> dict:
    """弃用版本"""
    
    # 不能弃用当前默认版本
    current = await self.get_default_version(agent_name)
    if current["version"] == version:
        raise ValueError("Cannot deprecate the default version")
    
    await self.db.execute(
        """
        UPDATE prompt_versions
        SET status = 'deprecated',
            deprecated_at = NOW()
        WHERE agent_name = :agent AND version = :version
        """,
        {"agent": agent_name, "version": version}
    )
    
    return {"agent_name": agent_name, "version": version, "status": "deprecated"}
```

---

## 5. A/B 测试

### 5.1 启用 A/B 测试

```python
async def enable_ab_test(
    self,
    agent_name: str,
    version_a: str,  # 当前版本
    version_b: str,  # 新版本
    traffic_percentage: float = 0.1,  # B 版本流量占比
    duration_days: int = 7
) -> dict:
    """启用 A/B 测试"""
    
    from datetime import timedelta
    
    end_date = datetime.now() + timedelta(days=duration_days)
    
    # 更新 B 版本配置
    await self.db.execute(
        """
        UPDATE prompt_versions
        SET ab_test_config = :config,
            status = 'testing'
        WHERE agent_name = :agent AND version = :version
        """,
        {
            "agent": agent_name,
            "version": version_b,
            "config": {
                "enabled": True,
                "traffic_percentage": traffic_percentage,
                "control_version": version_a,
                "start_date": datetime.now().isoformat(),
                "end_date": end_date.isoformat()
            }
        }
    )
    
    return {
        "agent_name": agent_name,
        "version_a": version_a,
        "version_b": version_b,
        "traffic_percentage": traffic_percentage,
        "end_date": end_date
    }
```

---

### 5.2 Agent 中集成 A/B 测试

```python
# app/agents/base.py
# 伪代码：BaseAgent 依赖 VersionService 的下列方法，需在 VersionService 中实现
#   _log_usage / get_default_version / get_ab_test_version / get_version / list_versions
import hashlib
from typing import Optional

from langchain_deepseek import ChatDeepSeek

from app.core.config import settings

class BaseAgent:
    """Agent 基类（增强版本管理）"""

    def __init__(self, config: "AgentConfig"):
        # 签名与 03-architecture/02-Agent详细设计.md §1.2 保持一致：BaseAgent.__init__(self, config: AgentConfig)
        self.config = config
        self.agent_name = config.name
        self.llm = ChatDeepSeek(
            model=settings.DEFAULT_LLM_MODEL,      # 模型 id 统一走配置，不写死
            temperature=config.temperature,
        )
        self.version_service = PromptVersionService()

    async def _select_prompt_version(self, routing_key: Optional[str] = None) -> dict:
        """选择 Prompt 版本（支持 A/B 测试）

        routing_key 必须是「稳定键」：优先 datasource_id，其次 conversation_id / user_id。
        """
        
        # 1. 获取默认版本
        default_version = await self.version_service.get_default_version(
            self.agent_name
        )
        
        # 2. 检查是否有正在进行的 A/B 测试
        ab_test_version = await self.version_service.get_ab_test_version(
            self.agent_name
        )
        
        if not ab_test_version:
            return default_version

        # 3. 无稳定键时不做随机分流：随机分流会让同一数据源跨版本，A/B 指标被污染
        if not routing_key:
            return default_version
        
        # 4. 按稳定键哈希分流（md5 跨进程稳定；Python 内置 hash() 带随机种子，禁止使用）
        traffic_pct = ab_test_version["ab_test_config"]["traffic_percentage"]
        hash_value = int(hashlib.md5(routing_key.encode("utf-8")).hexdigest(), 16)
        use_ab_version = (hash_value % 100) < (traffic_pct * 100)
        
        return ab_test_version if use_ab_version else default_version
    
    async def invoke(
        self,
        input_data: dict,
        routing_key: Optional[str] = None,
        version: Optional[dict] = None,
    ) -> dict:
        """执行 Agent（记录版本）"""
        
        # 1. 选择版本（显式传入的版本优先，用于回放/指定版本验证）
        selected = version or await self._select_prompt_version(routing_key)
        
        # 2. 加载 Prompt
        prompt = selected["system_prompt"]
        
        # 3. 执行
        import time
        start_time = time.time()
        
        try:
            result = await self.llm.ainvoke(prompt)
            duration = time.time() - start_time
            
            # 4. 记录使用
            await self._log_usage(
                version_id=selected["id"],
                version=selected["version"],
                duration=duration,
                success=True,
                result=result,
                routing_key=routing_key
            )
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            
            # 记录失败
            await self._log_usage(
                version_id=selected["id"],
                version=selected["version"],
                duration=duration,
                success=False,
                error=str(e),
                routing_key=routing_key
            )
            
            raise
```

---

### 5.3 A/B 测试报告

```python
# 伪代码片段：依赖 VersionService.self.db 与 self._get_quality_scores()
import numpy as np
from scipy import stats

async def get_ab_test_report(
    self,
    agent_name: str,
    version_a: str,
    version_b: str
) -> dict:
    """生成 A/B 测试报告"""
    
    # 查询两个版本的性能数据
    query = """
    SELECT 
        version,
        COUNT(*) as total_uses,
        AVG(duration) as avg_duration,
        AVG(cost) as avg_cost,
        AVG(quality_score) as avg_quality,
        SUM(CASE WHEN success THEN 1 ELSE 0 END)::FLOAT / COUNT(*) as success_rate
    FROM prompt_usage_logs
    WHERE agent_name = :agent 
      AND version IN (:version_a, :version_b)
      AND created_at >= NOW() - INTERVAL '7 days'
    GROUP BY version
    """
    
    results = await self.db.fetch_all(
        query,
        {"agent": agent_name, "version_a": version_a, "version_b": version_b}
    )
    
    # 按 version 建映射：GROUP BY 不保证返回顺序，绝不能用 results[0] / results[1]
    rows_by_version = {row["version"]: dict(row) for row in results}
    
    # 统计显著性检验
    from scipy import stats
    
    data_a = await self._get_quality_scores(agent_name, version_a)
    data_b = await self._get_quality_scores(agent_name, version_b)
    
    # scipy.stats.ttest_ind(a, b) 返回的 t 值符号含义：t > 0 表示 mean(a) > mean(b)。
    # 此处 a = 对照组 A，b = 实验组 B，所以：
    #   t_stat > 0 → B 版本更好；t_stat < 0 → A 版本更好（切勿写反）
    t_stat, p_value = stats.ttest_ind(data_a, data_b)
    
    if p_value >= 0.05:
        conclusion = "无显著差异"
    elif t_stat > 0:
        conclusion = (
            f"B 版本显著更好（B 均值 {np.mean(data_b):.2f} > A 均值 {np.mean(data_a):.2f}）"
        )
    else:
        conclusion = (
            f"A 版本显著更好（A 均值 {np.mean(data_a):.2f} > B 均值 {np.mean(data_b):.2f}）"
        )
    
    return {
        "version_a": {
            "version": version_a,
            "metrics": rows_by_version.get(version_a, {})
        },
        "version_b": {
            "version": version_b,
            "metrics": rows_by_version.get(version_b, {})
        },
        "statistical_test": {
            "t_statistic": t_stat,
            "p_value": p_value,
            "is_significant": p_value < 0.05,
            "conclusion": conclusion
        }
    }
```

---

## 6. 版本回滚

### 6.1 快速回滚

```python
# 伪代码片段：依赖 VersionService.self.db / activate_version / get_default_version
async def rollback_to_version(
    self,
    agent_name: str,
    target_version: str,
    reason: str = None,
    trigger_type: str = "manual"
) -> dict:
    """回滚到指定版本"""
    
    # 1. 验证目标版本存在且未被弃用
    target = await self.db.fetch_one(
        """
        SELECT id, version, status 
        FROM prompt_versions
        WHERE agent_name = :agent AND version = :version
        """,
        {"agent": agent_name, "version": target_version}
    )
    
    if not target:
        raise ValueError(f"Version {target_version} not found")
    
    if target["status"] == "deprecated":
        raise ValueError(f"Cannot rollback to deprecated version {target_version}")
    
    # 2. 先读出「回滚前正在生效的版本」
    #    ⚠️ 必须在 activate 之前读！否则 activate 已把 is_default 移到目标版本，
    #       查出来的 from_version 会等于 to_version，回滚日志失真。
    current = await self.db.fetch_one(
        """
        SELECT id, version
        FROM prompt_versions
        WHERE agent_name = :agent AND is_default = TRUE
        """,
        {"agent": agent_name}
    )
    from_version = current["version"] if current else None
    
    if from_version == target_version:
        return {
            "agent_name": agent_name,
            "rolled_back_to": target_version,
            "status": "noop",
            "reason": "target version is already the default"
        }
    
    # 3. 激活目标版本
    await self.activate_version(agent_name, target_version)
    
    # 4. 记录回滚日志（表结构见 3.3 version_rollback_logs）
    await self.db.execute(
        """
        INSERT INTO version_rollback_logs (
            agent_name, from_version, to_version, reason, trigger_type
        ) VALUES (
            :agent, :from_version, :to_version, :reason, :trigger_type
        )
        """,
        {
            "agent": agent_name,
            "from_version": from_version or "unknown",
            "to_version": target_version,
            "reason": reason or "Manual rollback",
            "trigger_type": trigger_type
        }
    )
    
    return {
        "agent_name": agent_name,
        "from_version": from_version,
        "rolled_back_to": target_version,
        "status": "success"
    }
```

---

### 6.2 自动回滚（基于错误率）

```python
# 伪代码片段：依赖 get_default_version / get_previous_stable_version / send_alert
# （均在 VersionService 中实现；告警走 Loguru + Prometheus + SMTP）
async def auto_rollback_check(self, agent_name: str):
    """自动检查是否需要回滚"""
    
    # 获取当前版本
    current = await self.get_default_version(agent_name)
    
    # 检查最近 1 小时的错误率
    stats = await self.db.fetch_one(
        """
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN NOT success THEN 1 ELSE 0 END) as errors
        FROM prompt_usage_logs
        WHERE agent_name = :agent 
          AND version = :version
          AND created_at >= NOW() - INTERVAL '1 hour'
        """,
        {"agent": agent_name, "version": current["version"]}
    )
    
    if stats["total"] < 10:
        return  # 样本太少，不判断
    
    error_rate = stats["errors"] / stats["total"]
    
    # 错误率 > 20% 时自动回滚
    if error_rate > 0.2:
        # 回滚到上一个稳定版本
        previous = await self.get_previous_stable_version(agent_name)
        
        if previous:
            await self.rollback_to_version(
                agent_name,
                previous["version"],
                reason=f"Auto rollback: error rate {error_rate:.1%}",
                trigger_type="auto"
            )
            
            # 发送告警
            await self.send_alert(
                level="critical",
                message=f"{agent_name} auto-rolled back due to high error rate"
            )
```

---

## 7. 实现代码

### 7.1 完整的 Agent 实现

```python
# app/agents/cleaning_agent.py
# 伪代码：VersionService.get_version 见 4.1，BaseAgent 见 5.2
from app.agents.base import BaseAgent

class DataCleaningAgent(BaseAgent):
    """数据清洗 Agent（版本管理增强）"""
    
    def __init__(self, config):
        # 与 02-Agent详细设计.md 一致：BaseAgent.__init__(self, config: AgentConfig)
        super().__init__(config)
    
    async def clean(
        self,
        raw_data: str,
        datasource_id: str = None,
        user_id: str = None,
        version: str = None  # 可选：指定版本（回放 / 灰度验证）
    ) -> dict:
        """清洗数据"""
        
        # 1. 确定本次使用的 Prompt 版本
        if version:
            prompt_version = await self.version_service.get_version(
                self.agent_name, version
            )
        else:
            # 用 datasource_id 作为稳定分流键，保证同一数据源始终命中同一版本
            prompt_version = await self._select_prompt_version(
                routing_key=datasource_id or user_id
            )
        
        # 2. 显式把选中的版本传进执行逻辑，确保 version 参数真正生效
        #    （原实现取了 prompt_version 却没用，指定版本形同虚设）
        result = await self.invoke(
            {"raw_data": raw_data, "datasource_id": datasource_id},
            routing_key=datasource_id or user_id,
            version=prompt_version
        )
        
        return result
```

---

### 7.2 API 端点

```python
# app/api/v1/prompt_versions.py
# 伪代码：list_versions 需在 PromptVersionService 中实现
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/prompt-versions", tags=["Prompt 版本管理"])

@router.get("/{agent_name}")
async def list_versions(agent_name: str):
    """列出所有版本"""
    service = PromptVersionService()
    return await service.list_versions(agent_name)

@router.post("/{agent_name}")
async def create_version(agent_name: str, data: dict):
    """创建新版本"""
    service = PromptVersionService()
    return await service.create_version(agent_name, **data)

@router.post("/{agent_name}/{version}/activate")
async def activate(agent_name: str, version: str):
    """激活版本"""
    service = PromptVersionService()
    return await service.activate_version(agent_name, version)

@router.post("/{agent_name}/ab-test")
async def start_ab_test(agent_name: str, data: dict):
    """启动 A/B 测试"""
    service = PromptVersionService()
    return await service.enable_ab_test(agent_name, **data)

@router.get("/{agent_name}/ab-test/report")
async def ab_test_report(agent_name: str, version_a: str, version_b: str):
    """A/B 测试报告"""
    service = PromptVersionService()
    return await service.get_ab_test_report(agent_name, version_a, version_b)

@router.post("/{agent_name}/rollback")
async def rollback(agent_name: str, target_version: str, reason: str = None):
    """回滚版本"""
    service = PromptVersionService()
    return await service.rollback_to_version(agent_name, target_version, reason)
```

---

## 📊 使用流程示例

### 开发新 Prompt 版本

```bash
# 1. 创建新版本（draft）
POST /api/v1/prompt-versions/cleaning_agent
{
  "version": "v1.2.0",
  "system_prompt": "...",
  "description": "优化去重逻辑"
}

# 2. 本地测试
# 使用指定版本测试
result = await cleaning_agent.clean(data, version="v1.2.0")

# 3. 启动 A/B 测试（10% 流量）
POST /api/v1/prompt-versions/cleaning_agent/ab-test
{
  "version_a": "v1.1.0",
  "version_b": "v1.2.0",
  "traffic_percentage": 0.1,
  "duration_days": 7
}

# 4. 查看 A/B 测试报告
GET /api/v1/prompt-versions/cleaning_agent/ab-test/report?version_a=v1.1.0&version_b=v1.2.0

# 5. 如果 B 版本更好，激活它
POST /api/v1/prompt-versions/cleaning_agent/v1.2.0/activate

# 6. 如果出现问题，回滚
POST /api/v1/prompt-versions/cleaning_agent/rollback
{
  "target_version": "v1.1.0",
  "reason": "错误率过高"
}
```

---

## ✅ 改进总结

### 解决的问题

✅ 多版本并存和管理  
✅ A/B 测试机制  
✅ 版本回滚流程  
✅ 性能指标追踪  
✅ 自动化运维（自动回滚）  

### 核心价值

🎯 **数据驱动优化**：基于真实数据决策，而非主观判断  
🔄 **持续迭代**：安全地测试新版本，不影响生产  
🛡️ **风险控制**：出现问题快速回滚，降低影响  
📊 **可观测性**：每个版本的效果一目了然  

---

**Prompt 版本管理方案完成！** ✅
