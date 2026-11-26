# M4-A PR-4 scope：后台任务 tenant context + audit 扩展

> 状态：`draft_scope`（2026-11-26，**未批准**；不写代码、不加 migration）
> 前置：PR-3 accepted for local/test；staging flag=true 冒烟尚未执行
> 边界：本文件只定义 PR-4 范围与验收；PR-4 代码、026 migration、生产 migration 均需单独批准
> 不做：retention、alerting、cost 预算、RLS、M1/Judge 变更

## 1. 现状事实

### 1.1 Celery 任务与写入

| 任务 | 入口 | 写入 / 副作用 | 当前 tenant 来源 | 现状 |
|---|---|---|---|---|
| `tasks.clean_datasource` | `cleaning.py` → `run_clean_task` | `tasks`、`cleaned_data`、`raw_data.status`，可能建 structure 子任务 | 父 `Task` / `RawData` | 显式 tenant；PR-3 已覆盖 |
| `tasks.structure_raw` | `structure.py` → `run_structure_task` | `tasks`、`raw_data`、`knowledge_base`、`analysis_results` | `RawData.tenant_id` | 显式 tenant；PR-3 已覆盖 |
| `tasks.evaluate_datasource` | `evaluation.py` | `tasks`、`analysis_results` | `Task.tenant_id` | 显式 tenant |
| `tasks.analyze_insights` | `insight.py` | `tasks`、`analysis_results` | `Task.tenant_id` | 显式 tenant |
| `tasks.extract_knowledge` | `knowledge.py` | `tasks`、`knowledge_base`、`knowledge_gaps` | `Task.tenant_id` | 显式 tenant |
| `tasks.generate_report` | `report.py` | `reports`、`tasks`、报告文件 | `Report.tenant_id` | 显式 tenant |
| `tasks.rag_evaluation` | `rag_evaluation.py` → runner | `rag_evaluation_runs/results`、`rag_traces`、`tasks` | `Run.tenant_id` + `system_context` | PR-3 已补 |
| `tasks.recover_stale_rag_runs` | `rag_evaluation.py` | `rag_evaluation_runs`、`tasks` 状态 | `Run.tenant_id` | 尚无显式 context；需 PR-4 审计 |
| `tasks.weekly_digest` | `digest.py` | 只读聚合 + 邮件；不写业务表 | 无（平台级） | 跨全租户聚合；需明确平台级语义 |
| `tasks.monitor_cost` | `cost_monitor.py` | 只读 `llm_calls`；日志/告警 | 无（平台级） | 全局成本；需明确平台级语义 |
| `tasks.ping` | `__init__.py` | 无 | 无 | 无需处理 |

### 1.2 audit_logs 现状

| 项 | 现状 |
|---|---|
| 字段 | `id` / `user_id` / `tenant_id`(nullable) / `action` / `resource_type` / `resource_id` / `details` JSONB / `ip_address` / `user_agent` / `created_at` |
| 已有写入 | platform_admin 跨租户访问（`tenant.cross_access`）；凭据 create/update/delete（`details.provider`，`tenant_id` 为空） |
| 未覆盖 | 数据源/报告删除、任务取消/重试、platform_admin 写操作、租户状态变更、批量导出 |
| before/after | 无；只能记录调用参数/摘要 |
| append-only | 仅应用层未提供 update/delete；DB 无强制 |
| 密钥安全 | 凭据审计不含 Key；PR-4 需白名单脱敏 |

## 2. PR-4 目标

1. **后台任务 tenant context 覆盖清单落地**：所有写业务表的 Celery 任务显式带 tenant，不依赖隐式用户租户。
2. **平台级任务语义明确**：digest / cost monitor 保持平台级聚合，不错误套用租户过滤；在代码/注释/测试中固定。
3. **audit 扩展**：新增 `tenant_id` 必填规则（有 actor 时）、`before` / `after` 快照、append-only 保护；敏感字段脱敏。
4. **staging 验证步骤**：在 staging 025 通过后，补 PR-4 的审计/后台任务验证，不改变 PR-3 staging 门槛。

## 3. 后台任务 tenant context 设计

### 3.1 原则

- 任务入口只接收资源 ID；从 DB 加载父资源后，用 `system_context(parent.tenant_id, actor_user_id=...)` 显式 attach。
- 子资源写入用父资源 tenant：`Task` / `RawData` / `Report` / `Run`；禁止从环境变量或默认租户兜底。
- 平台级任务（digest / cost monitor）不 attach 业务 tenant；不得写业务表；日志中标记 `scope=platform`。
- `recover_stale_rag_runs` 逐 Run 处理：每个 Run 用自身 `tenant_id`；状态更新不得跨 Run 混用。审计可选：记录 `run.recovered_stale`（若 PR-4 audit 扩展到系统事件）。

### 3.2 覆盖矩阵（实施时逐项打勾）

| 任务 | 写入表 | tenant 来源 | 现有测试 | PR-4 动作 |
|---|---|---|---|---|
| clean | tasks / cleaned_data / raw_data | Task / RawData | 有 | 维持 + 补 context 断言 |
| structure | tasks / raw_data / knowledge_base / analysis_results | RawData | 有 | 维持 |
| evaluate | tasks / analysis_results | Task | 有 | 维持 |
| insight | tasks / analysis_results | Task | 有 | 维持 |
| extract | tasks / knowledge_base / knowledge_gaps | Task | 有 | 维持 |
| report | reports / tasks / file | Report | 有 | 维持 |
| rag_evaluation | runs / results / traces / tasks | Run | 有 | 维持 |
| recover_stale | runs / tasks | Run | 部分 | 补显式 context + 测试 |
| weekly_digest | 无 | 平台级 | 有 | 固定 `scope=platform`；禁止写业务表 |
| monitor_cost | 无 | 平台级 | 有 | 同上 |

## 4. audit 扩展设计

### 4.1 Schema（建议，最终 migration 单独评审）

| 字段 | 类型 | 说明 |
|---|---|---|
| `tenant_id` | UUID nullable | 有租户上下文时必须写；平台级事件可为 NULL |
| `before` | JSONB nullable | 变更前安全快照；仅白名单字段 |
| `after` | JSONB nullable | 变更后安全快照；仅白名单字段 |
| `request_id` | varchar(64) nullable | 可选：串联一次请求/任务 |

> 是否新增 `before`/`after` 列，还是放入 `details`，在实施评审时定；本 scope 只固定“可查询、可脱敏、不可篡改”的要求。

### 4.2 审计事件（P1 最小集）

| 事件 | action | tenant_id | before/after |
|---|---|---|---|
| platform_admin 切租户访问 | `tenant.cross_access` | target tenant | 保留现有 details；可加 request_id |
| 凭据 create / update / delete | `credential.create/update/delete` | actor tenant | 仅 provider、指纹/掩码，不含 Key |
| 数据源删除 / 强制删除 | `datasource.delete` | datasource tenant | 名称、类型、级联计数 |
| 报告删除 | `report.delete` | report tenant | 标题、格式、状态 |
| 任务取消 / 重试 | `task.cancel/retry` | task tenant | 状态前后 |
| 租户状态变更（platform_admin） | `tenant.update` | target tenant | status before/after |

> 导出/对比等读操作不默认写审计；如合规需要，单独加“导出审计”事件，避免日志膨胀。

### 4.3 append-only

- 应用层：不提供 update/delete audit API；repository 只 `add`。
- DB 层建议二选一（实施评审）：
  1. 撤销应用角色的 `UPDATE/DELETE` 权限；
  2. `BEFORE UPDATE OR DELETE` trigger 直接 `RAISE EXCEPTION`。
- 测试：直接 SQL `UPDATE audit_logs` / `DELETE` 必须失败（或应用层无入口）；新增测试不依赖真实权限时用 trigger。
- 历史行：不要求回填 `before/after`；`tenant_id` 保持现状，新增事件必须写。

### 4.4 脱敏

- 白名单序列化：只记录名称、状态、类型、计数、provider、掩码指纹。
- 禁止记录：API Key、Authorization、Cookie、密码、完整 prompt/response（除非已有单独脱敏策略）。
- 测试：构造含 `api_key` / `password` 的 payload，断言审计中不出现原值。

## 5. staging 验证步骤（PR-4 部分）

> 前提：PR-3 staging 025 已通过；PR-4 代码另行部署到 staging。

| # | 验证 | 预期 |
|---|---|---|
| 1 | 凭据 create/update/delete | `audit_logs.tenant_id` 为 actor tenant；无 Key 明文 |
| 2 | 数据源删除 | 审计 before/after 含名称/类型/级联计数 |
| 3 | 任务取消/重试 | 审计状态前后正确 |
| 4 | `recover_stale_rag_runs` | 每个 Run 的 tenant 不混用；Task 状态同步 |
| 5 | digest / cost monitor | 不写业务表；日志 `scope=platform` |
| 6 | append-only | UPDATE/DELETE 被拒绝 |
| 7 | 跨租户 | 既有 404 矩阵不回归 |

## 6. 拆分建议（均需单独批准）

| 子项 | 内容 | 是否含 migration |
|---|---|---|
| PR-4a | 后台任务 context 覆盖 + recover_stale 显式 context + 测试 | 否 |
| PR-4b | audit before/after/request_id + append-only + 脱敏 + 测试 | 是（新 migration，编号实施时定） |
| PR-4c | staging 验证记录 + 回滚/监控补充 | 否 |

## 7. 非目标

- retention / 归档 / 审计查询 UI；
- alerting / cost 预算调整；
- RLS；
- 生产 migration；
- M1 / Judge / target / baseline / 10/40；
- 批量搬迁旧对象（仍另开 job）。

## 8. 验收标准

- 覆盖矩阵中所有写业务表的任务均有显式 tenant 来源和测试；
- 平台级任务不误写业务表，语义固定；
- audit 事件含 tenant_id，before/after 可查询且脱敏；
- append-only 有可执行测试；
- staging 验证 1–7 通过并留证据；
- 不碰生产；不改变 PR-3 staging 门槛。

## 9. 待决策

1. `before/after` 用独立列还是 `details` 子对象？
2. append-only 用权限还是 trigger？应用角色是否与迁移角色分离？
3. 导出/对比是否纳入审计 P1？
4. `recover_stale_rag_runs` 是否写系统审计事件？
