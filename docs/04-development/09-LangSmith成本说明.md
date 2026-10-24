# LangSmith 成本说明与替代方案

> **文档版本**：v1.0  
> **创建日期**：2026年10月23日  
> **变更类型**：成本预算补充

---

## 📋 LangSmith 定价

### 官方定价（2026年）

| 计划 | 月费 | Trace 数量 | 适用场景 |
|------|------|-----------|----------|
| **Developer** | $0 | 5,000 traces/月 | 开发测试 |
| **Plus** | $39 | 50,000 traces/月 | 小型项目 |
| **Team** | $199 | 500,000 traces/月 | 中型项目 |
| **Enterprise** | 定制 | 无限制 | 大型企业 |

**超出部分**：$0.001/trace

---

## 📊 实际使用量估算

### 场景 1：小型企业（1万条/月）

```
Agent 调用次数：
- 数据清洗：10,000 次
- 质量评估：10,000 次
- 知识提取：100 次（批量）
总计：20,100 traces/月

建议计划：Developer（免费）或 Plus ($39)
```

---

### 场景 2：中型企业（10万条/月）

```
Agent 调用次数：
- 数据清洗：100,000 次
- 质量评估：100,000 次
- 知识提取：1,000 次（批量）
总计：201,000 traces/月

建议计划：Team ($199)
或 Plus + 超出费用：$39 + (201,000 - 50,000) × $0.001 = $190
```

---

### 场景 3：大型企业（100万条/月）

```
Agent 调用次数：
- 数据清洗：1,000,000 次
- 质量评估：1,000,000 次
- 知识提取：10,000 次（批量）
总计：2,010,000 traces/月

建议计划：Enterprise（定制）
估算成本：$500-$1,000/月
```

---

## 💰 更新后的成本预算

### 小型企业（1万条/月）

| 服务 | 月成本 | 备注 |
|------|--------|------|
| LLM Token | $84.90 | |
| 基础设施 | $65.00 | |
| **LangSmith** | **$0-$39** | **Developer 免费或 Plus** |
| **总计** | **$149.90-$188.90** | |

---

### 中型企业（10万条/月）

| 服务 | 月成本 | 备注 |
|------|--------|------|
| LLM Token | $849.00 | |
| 基础设施 | $380.00 | |
| **LangSmith** | **$199.00** | **Team 计划（推荐）** |
| **总计** | **$1,428.00** | |

**或使用 Plus + 超出**：$1,268.00（省 $160）

---

### 大型企业（100万条/月）

| 服务 | 月成本 | 备注 |
|------|--------|------|
| LLM Token | $8,490.00 | |
| 基础设施 | $1,950.00 | |
| **LangSmith** | **$500-$1,000** | **Enterprise 定制** |
| 其他监控 | $100.00 | Sentry 等 |
| **总计** | **$11,040-$11,540** | |

---

## 🔄 替代方案：自建可观测性

### 方案对比

| 维度 | LangSmith | 自建（Prometheus + Grafana） |
|------|-----------|----------------------------|
| **成本** | $39-$199/月 | **$0**（开源） |
| **部署难度** | ⭐ 简单（SaaS） | ⭐⭐⭐ 中等（自己部署） |
| **功能完整度** | ⭐⭐⭐⭐⭐ 专为 LangChain 设计 | ⭐⭐⭐ 通用监控 |
| **Trace 查看** | ✅ 原生支持 | ❌ 需自己实现 |
| **Prompt 管理** | ✅ 支持 | ❌ 不支持 |
| **A/B 测试** | ✅ 支持 | ❌ 需自己实现 |
| **维护成本** | 低 | 中 |

---

### 自建方案实现

如果选择自建，需要实现以下功能：

```python
# app/core/observability.py
from prometheus_client import Counter, Histogram, Gauge
import logging

# 1. 基础指标
agent_calls_total = Counter(
    'agent_calls_total',
    'Total agent calls',
    ['agent_name', 'status']
)

agent_duration = Histogram(
    'agent_duration_seconds',
    'Agent execution duration',
    ['agent_name']
)

agent_token_usage = Counter(
    'agent_token_usage_total',
    'Total tokens used',
    ['agent_name', 'token_type']
)

agent_cost = Counter(
    'agent_cost_dollars_total',
    'Total cost in dollars',
    ['agent_name']
)

# 2. 在 Agent 中集成
class ObservableAgent(BaseAgent):
    async def invoke(self, input_data: dict) -> dict:
        import time
        start_time = time.time()
        
        try:
            result = await super().invoke(input_data)
            
            # 记录成功指标
            agent_calls_total.labels(
                agent_name=self.__class__.__name__,
                status='success'
            ).inc()
            
            duration = time.time() - start_time
            agent_duration.labels(
                agent_name=self.__class__.__name__
            ).observe(duration)
            
            # 记录 Token 和成本
            if 'token_usage' in result:
                agent_token_usage.labels(
                    agent_name=self.__class__.__name__,
                    token_type='input'
                ).inc(result['token_usage']['input'])
                
                agent_token_usage.labels(
                    agent_name=self.__class__.__name__,
                    token_type='output'
                ).inc(result['token_usage']['output'])
            
            if 'cost' in result:
                agent_cost.labels(
                    agent_name=self.__class__.__name__
                ).inc(result['cost'])
            
            return result
            
        except Exception as e:
            agent_calls_total.labels(
                agent_name=self.__class__.__name__,
                status='error'
            ).inc()
            raise
```

**Grafana Dashboard 配置**：

```yaml
# grafana/dashboards/agent_monitoring.json
{
  "dashboard": {
    "title": "Agent 监控",
    "panels": [
      {
        "title": "Agent 调用次数",
        "type": "graph",
        "targets": [{
          "expr": "rate(agent_calls_total[5m])"
        }]
      },
      {
        "title": "平均响应时间",
        "type": "graph",
        "targets": [{
          "expr": "rate(agent_duration_seconds_sum[5m]) / rate(agent_duration_seconds_count[5m])"
        }]
      },
      {
        "title": "Token 使用量",
        "type": "graph",
        "targets": [{
          "expr": "rate(agent_token_usage_total[5m])"
        }]
      },
      {
        "title": "实时成本",
        "type": "stat",
        "targets": [{
          "expr": "sum(agent_cost_dollars_total)"
        }]
      }
    ]
  }
}
```

---

## 🎯 建议

### MVP 阶段（前 3 个月）

**推荐**：使用 **LangSmith Developer**（免费）

**理由**：
- ✅ 无成本
- ✅ 快速集成
- ✅ 专业的 Trace 查看
- ✅ 5,000 traces 足够测试

---

### 生产阶段（中小规模）

**推荐**：**LangSmith Plus** ($39/月)

**理由**：
- ✅ 成本可控
- ✅ 50,000 traces/月足够大多数场景
- ✅ 省去自建维护成本
- ⚠️ 超出后按需付费

---

### 生产阶段（大规模）

**两种选择**：

**选择 1：LangSmith Team/Enterprise**
- ✅ 功能完整
- ✅ 专业支持
- ❌ 成本较高 ($199+)

**选择 2：自建（Prometheus + Grafana）**
- ✅ 成本低（只需服务器）
- ✅ 完全可控
- ❌ 需要开发工作量
- ❌ 功能不如 LangSmith 完整

**建议**：
- 如果**预算充足**，使用 LangSmith（省时省力）
- 如果**成本敏感**，自建可观测性（省钱但需投入开发）

---

## 📝 更新记录

| 日期 | 变更 |
|------|------|
| 2026-10-23 | 将 LangSmith 成本纳入预算 |
| 2026-10-23 | 添加自建可观测性替代方案 |
| 2026-10-23 | 更新月度和年度成本预算 |

---

**成本预算更新完成！** ✅
