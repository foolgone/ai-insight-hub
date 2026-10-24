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

---

## 3. 数据库设计

### 3.1 Prompt 版本表

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

### 3.2 Prompt 使用记录表

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
    cost FLOAT,                 -- 成本（美元）
    
    -- 质量数据
    success BOOLEAN,
    error_message TEXT,
    quality_score FLOAT,        -- 输出质量评分
    
    -- 时间戳
    created_at TIMESTAMP DEFAULT NOW()
) PARTITION BY RANGE (created_at);

-- 按月分区
CREATE TABLE prompt_usage_logs_2026_10 PARTITION OF prompt_usage_logs
    FOR VALUES FROM ('2026-10-01') TO ('2026-11-01');

CREATE TABLE prompt_usage_logs_2026_11 PARTITION OF prompt_usage_logs
    FOR VALUES FROM ('2026-11-01') TO ('2026-12-01');

-- 索引
CREATE INDEX idx_prompt_usage_agent_version 
    ON prompt_usage_logs(agent_name, version, created_at);
CREATE INDEX idx_prompt_usage_prompt_id 
    ON prompt_usage_logs(prompt_version_id, created_at);
```

---

## 4. 版本管理流程

### 4.1 创建新版本

```python
# app/services/prompt_version_service.py
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
        version_id = await self.db.execute(
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
import random

class BaseAgent:
    """Agent 基类（增强版本管理）"""
    
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.version_service = PromptVersionService()
    
    async def _select_prompt_version(self, user_id: str = None) -> dict:
        """选择 Prompt 版本（支持 A/B 测试）"""
        
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
        
        # 3. 根据流量分配决定使用哪个版本
        traffic_pct = ab_test_version["ab_test_config"]["traffic_percentage"]
        
        # 使用 user_id 哈希保证同一用户始终使用同一版本
        if user_id:
            hash_value = int(hashlib.md5(user_id.encode()).hexdigest(), 16)
            use_ab_version = (hash_value % 100) < (traffic_pct * 100)
        else:
            use_ab_version = random.random() < traffic_pct
        
        return ab_test_version if use_ab_version else default_version
    
    async def invoke(self, input_data: dict, user_id: str = None) -> dict:
        """执行 Agent（记录版本）"""
        
        # 1. 选择版本
        version = await self._select_prompt_version(user_id)
        
        # 2. 加载 Prompt
        prompt = version["system_prompt"]
        
        # 3. 执行
        import time
        start_time = time.time()
        
        try:
            result = await self.llm.ainvoke(prompt)
            duration = time.time() - start_time
            
            # 4. 记录使用
            await self._log_usage(
                version_id=version["id"],
                version=version["version"],
                duration=duration,
                success=True,
                result=result,
                user_id=user_id
            )
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            
            # 记录失败
            await self._log_usage(
                version_id=version["id"],
                version=version["version"],
                duration=duration,
                success=False,
                error=str(e),
                user_id=user_id
            )
            
            raise
```

---

### 5.3 A/B 测试报告

```python
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
    
    # 统计显著性检验
    from scipy import stats
    
    data_a = await self._get_quality_scores(agent_name, version_a)
    data_b = await self._get_quality_scores(agent_name, version_b)
    
    t_stat, p_value = stats.ttest_ind(data_a, data_b)
    
    return {
        "version_a": {
            "version": version_a,
            "metrics": results[0] if results else {}
        },
        "version_b": {
            "version": version_b,
            "metrics": results[1] if len(results) > 1 else {}
        },
        "statistical_test": {
            "t_statistic": t_stat,
            "p_value": p_value,
            "is_significant": p_value < 0.05,
            "conclusion": "B 版本显著更好" if p_value < 0.05 and t_stat > 0 else "无显著差异"
        }
    }
```

---

## 6. 版本回滚

### 6.1 快速回滚

```python
async def rollback_to_version(
    self,
    agent_name: str,
    target_version: str,
    reason: str = None
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
    
    # 2. 激活目标版本
    await self.activate_version(agent_name, target_version)
    
    # 3. 记录回滚日志
    await self.db.execute(
        """
        INSERT INTO version_rollback_logs (
            agent_name, from_version, to_version, reason
        ) VALUES (
            :agent, 
            (SELECT version FROM prompt_versions 
             WHERE agent_name = :agent AND is_default = TRUE),
            :to_version,
            :reason
        )
        """,
        {
            "agent": agent_name,
            "to_version": target_version,
            "reason": reason or "Manual rollback"
        }
    )
    
    return {
        "agent_name": agent_name,
        "rolled_back_to": target_version,
        "status": "success"
    }
```

---

### 6.2 自动回滚（基于错误率）

```python
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
                reason=f"Auto rollback: error rate {error_rate:.1%}"
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
from app.agents.base import BaseAgent

class DataCleaningAgent(BaseAgent):
    """数据清洗 Agent（版本管理增强）"""
    
    def __init__(self):
        super().__init__(agent_name="cleaning_agent")
    
    async def clean(
        self,
        raw_data: str,
        user_id: str = None,
        version: str = None  # 可选：指定版本
    ) -> dict:
        """清洗数据"""
        
        # 如果指定版本，使用指定版本；否则自动选择
        if version:
            prompt_version = await self.version_service.get_version(
                self.agent_name, version
            )
        else:
            prompt_version = await self._select_prompt_version(user_id)
        
        # 执行清洗
        result = await self.invoke(
            {"raw_data": raw_data},
            user_id=user_id
        )
        
        return result
```

---

### 7.2 API 端点

```python
# app/api/v1/prompt_versions.py
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
