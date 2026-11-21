# Phase 3D · 真实 WeKnora 联调报告

**日期**：2026-11-14
**环境**：本地虚拟机 `192.168.150.100`（4C / 7.5G / Docker 29.3.1）
**结论**：**通过**。真实 retrieve、真实 query、Trace 落库/读取、配置指纹、一次真实批量评测 Run 均验证成功；未使用公司实例 `10.248.37.95`。

---

## 1. 部署

WeKnora 源码：`https://github.com/Tencent/WeKnora`（VERSION `0.9.0`，镜像 `latest`）
部署目录：`/opt/weknora`（compose + config + `.env`，`.env` 权限 600）

| 服务 | 镜像 | 端口 |
|---|---|---|
| app | `wechatopenai/weknora-app:latest` | `8080` |
| frontend | `wechatopenai/weknora-ui:latest` | `8081` |
| docreader | `wechatopenai/weknora-docreader:latest` | 内部 50051 |
| postgres | `paradedb/paradedb:v0.25.11-pg17` | 内部 5432 |
| redis | `redis:7.0-alpine` | 内部 6379 |

模型（OpenAI 兼容）：

| 类型 | 模型 | 维度/上下文 |
|---|---|---|
| KnowledgeQA | `qwen-plus`（DashScope compatible） | 131072 |
| Embedding | `text-embedding-v3`（DashScope compatible） | 1024 |

健康检查：`GET http://192.168.150.100:8080/health` → `{"status":"ok"}`。

数据准备：

- 注册用户 `phase3d-2@weknora.local` → 空间 `10001`
- 临时知识库 `phase3d-verify-*`（`4ae8e147-6f76-4330-93f1-d2b3fef3d9ba`）
- 上传 `phase3d_doc.md`（退款/发票/发货/物流），解析 `completed`
- Agent `phase3d-agent`（`2c74bf39-bc41-4bf0-a64a-4a1f24721a46`，quick-answer，绑定该 KB）
- API Key：full-access（明文仅保存在本地临时目录，未入库/未提交）

---

## 2. 真实调用结果

| 项 | retrieve | query |
|---|---|---|
| Trace ID | `7f316acc-67f4-4b1f-8f9e-24cf373169b9` | `28280552-4376-4f19-a3a0-3d448b08299f` |
| 状态 | `success` | `success` |
| context_source | `hybrid_search` | `agent_chat` |
| contexts | 2 条 | 2 条 |
| context_available | `true` | `true` |
| answer | —（检索模式） | 378 字 |
| latency | 371 ms | 4724 ms |
| missing | `token_usage` | `token_usage` |

Trace 中的请求配置指纹（`retrieval_config._request_config`）：

```json
{"top_k": 5, "agent_id": "2c74bf39-...", "tenant_id": "10001",
 "knowledge_base_id": "4ae8e147-...", "precision_mode": "at_k", "split": "test"}
```

query 的 `model_config.agent_id` 同时记录 Agent；两条 Trace 均能从 DB 按幂等键读回（`read_back=true`）。

### 2.1 原始响应核对

- retrieve：原始 `data` 2 条 ↔ Trace contexts 2 条；`knowledge_id` 全部匹配；content 去首尾空白后逐条相等。
- query：原始 SSE `references.knowledge_references` 2 条 ↔ Trace contexts 2 条；`id`（chunk）与 `knowledge_id`（doc）全部匹配；`answer` 事件拼接长度 = Trace answer 长度（378）。
- 检索结果包含 `score`（0.695 / 0.645），与 Phase 0「实测无 score」的旧结论不同，按「有则记录」处理。

### 2.2 真实批量评测 Run

| 项 | 值 |
|---|---|
| Run ID | `aa22c1e4-a435-44f6-850a-38972c096212` |
| 模式 | retrieve（adapter=weknora） |
| 条目 | 1（gold 证据取真实首条 context 的 document_id） |
| 状态 | `completed`，failed=0 |
| 指标 | hit_rate / mrr / context_recall / context_precision_at_k 均为 **1.0** |
| Trace | contexts=2，source=`hybrid_search`，latency=223ms |

> 该 Run 的 `result` 证明：真实检索 → Trace → 指标 → 结果 → 汇总全链路可用。
> 联调产生的 Run/Task/Trace/Dataset 已从开发库清理，避免污染全局计数测试；证据保留在本报告与本地 JSON。

---

## 3. 发现并修复的问题

| # | 问题 | 修复 |
|---|---|---|
| 1 | WeKnora 0.9 的 SSE 把检索片段放在 `references.knowledge_references`，旧解析只认 `tool_result.data.results`，导致 query 被误判为 `context_source=none` | `_extract_contexts` 支持 `references` 事件（保留旧格式兼容）；chunk_id 取 `id`，metadata 记录 `chunk_index/chunk_type` |
| 2 | Trace 只记录适配器回显，KB/Agent/Tenant/Top-K 不进 Trace | `execute_query` 统一写入 `retrieval_config._request_config`（3C 只在批量执行器写入，现覆盖所有调用） |
| 3 | 测试用 Trace 总数断言受外部数据影响 | 幂等测试改为按 `idempotency_key` 统计（不放宽断言） |

外部字段缺口（非代码 bug）：

- `hybrid-search` 返回 `knowledge_id` 但没有 chunk id；query `references` 有 chunk id。
- `token_usage` 外部未返回 → `missing=["token_usage"]`，不补 0。
- query 的 references 含 `chunk_type=summary` 的摘要片段；它是实际生成上下文，Judge 时按原样使用。

---

## 4. 延迟与稳定性

| 调用 | 延迟 |
|---|---|
| retrieve（首次） | 1037 ms |
| retrieve（稳定） | 223–371 ms |
| query（首次） | 3534 ms |
| query（第二次） | 4724 ms |

异常：无 5xx、无超时、无重试；仅 `token_usage` 缺失。query 延迟主要是 LLM 生成（qwen-plus），符合外部服务预期。

---

## 5. 测试与回归

- 新增单测：`test_sse_parses_knowledge_references_event`（0.9 references 格式）
- 集成测试补充：Trace `_request_config` 持久化断言；幂等计数按 key 隔离
- 全量 `pytest -m "not prompt"`：**885 passed**（Phase 3C 884 + 1）
- mypy 0 / black / flake8 / lint-imports 5 kept
- 前端未改动

## 6. 遗留

1. API Key 目前只存本地临时文件，后续需要纳入 `user_llm_credentials`（Phase 4 或运维配置）。
2. `hybrid-search` 无 chunk id，检索指标目前按 `document_id` 匹配；若后续外部返回 chunk id，可提升到 chunk 级。
3. 真实 Judge 尚未开始（Phase 3E）。
4. `latest` 镜像未锁定 digest；上线前建议锁定 `weknora-*` 镜像 digest。
5. 本机 WeKnora 的 `.env` 含 DashScope/DB/Redis 密钥，权限 600；不得提交仓库。
