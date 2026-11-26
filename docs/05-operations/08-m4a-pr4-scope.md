# M4-A PR-4 scope：后台任务 tenant context + audit 扩展

> 状态：`draft_scope`（2026-11-26，P1 revision 4；**scope draft accepted，implementation 未批准**）
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
| `tasks.recover_stale_rag_runs` | `rag_evaluation.py` | `rag_evaluation_runs`、`tasks` 状态 | `Run.tenant_id` | 尚无显式 context；PR-4a 必补 |
| `tasks.weekly_digest` | `digest.py` | 只读聚合 + 邮件；不写业务表 | 无（平台级） | 跨全租户聚合；固定平台级语义 |
| `tasks.monitor_cost` | `cost_monitor.py` | 只读 `llm_calls`；日志/告警 | 无（平台级） | 全局成本；固定平台级语义 |
| `tasks.ping` | `__init__.py` | 无 | 无 | 无需处理 |

### 1.2 audit_logs 现状

| 项 | 现状 |
|---|---|
| 字段 | `id` / `user_id` / `tenant_id`(nullable) / `action` / `resource_type` / `resource_id` / `details` JSONB / `ip_address` / `user_agent` / `created_at` |
| 已有写入 | platform_admin 跨租户访问（`tenant.cross_access`）；凭据 create/update/delete（`details.provider`，`tenant_id` 为空） |
| 未覆盖 | 登录成功/失败、token 撤销、报告生成/下载、数据导出、数据删除、任务取消/重试、租户状态变更、stale recovery |
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
- `recover_stale_rag_runs` 采用「平台级只读扫描 + 按 Run tenant 显式更新」；不要求用户请求上下文，但每次更新必须带 tenant 谓词。

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
| recover_stale | runs / tasks | Run（逐条） | 部分 | 补显式 context + tenant 谓词 + A/B 测试 |
| weekly_digest | 无 | 平台级 | 有 | 固定 `scope=platform`；禁止写业务表 |
| monitor_cost | 无 | 平台级 | 有 | 同上 |

### 3.3 `recover_stale_rag_runs` 方案（P1-1 已定）

采用 **平台级只读扫描 + 按 `run.tenant_id` 显式更新**：

1. 查询只读：扫描 `rag_evaluation_runs` 中 heartbeat 超时的 Run（跨租户只读，不需要 tenant 过滤）。
2. 每条 Run 独立处理：
   - `attach_tenant_context(user, system_context(run.tenant_id, actor_user_id=run.user_id))`（如加载 user）；
   - Run 状态更新必须带 tenant 谓词：
     `UPDATE rag_evaluation_runs SET status=... WHERE id=:run_id AND tenant_id=:tenant_id AND status='running' AND last_heartbeat_at < :cutoff`；
   - Task 状态更新同样带 `tenant_id`：`UPDATE tasks ... WHERE id=:task_id AND tenant_id=:tenant_id`。
3. 单条失败隔离：记录错误与 alert，不中断其他 Run；失败 Run 保持原状态，下个周期重试，不写入错误租户。
4. 审计：`run.recovered_stale` 为高风险事件，必须与 Run/Task 更新同事务写 `audit_outbox`；`tenant_id=run.tenant_id`，details 记录 run_id/task_id/old_status。

验收测试（PR-4a）：

- tenant A/B 各造 1 条 stale Run + 对应 Task；
- `TENANT_ENFORCEMENT_ENABLED=true` 执行 recovery；
- A/B 各自的 Run/Task 只被本租户更新；
- 构造错误 tenant 的更新尝试影响 0 行；
- 任务不因缺 TenantContext 失败；跨租户更新计数 = 0。

## 4. audit 扩展设计

### 4.1 Schema（026，PR-4b）

| 字段 | 类型 | 说明 |
|---|---|---|
| `tenant_id` | UUID nullable | 有租户上下文时必须写；平台级事件可为 NULL |
| `event_id` | UUID nullable, unique | 幂等键；高风险由 outbox 带入，低风险写入时生成；重复投递 `ON CONFLICT DO NOTHING` |
| `before` | JSONB nullable | 变更前安全快照；仅白名单字段 |
| `after` | JSONB nullable | 变更后安全快照；仅白名单字段 |
| `request_id` | varchar(64) nullable | 串联一次请求/任务（可选，写入时生成） |

> 采用独立 `before` / `after` 列，不放入 `details`，便于查询与脱敏测试；026 只加列，不改历史行。
> `event_id` 是 at-least-once 投递的幂等键：同一 outbox 重试两次，`audit_logs` 只有一条。

### 4.2 审计事件（P1 完整集）

| 事件 | action | tenant_id | before/after / details | 审计失败策略 |
|---|---|---|---|---|
| platform_admin 切租户访问 | `tenant.cross_access` | target tenant | 保留现有 details；加 request_id | **高风险：outbox** |
| 登录成功 | `login.success` | actor tenant | method / request_id；不含密码 | 低风险：best-effort |
| 登录失败 | `login.failure` | 可识别用户时 actor tenant，否则 NULL | reason / email hash / IP；不含密码 | 低风险：best-effort |
| token 撤销 | `token.revoke` | actor tenant | jti hash / reason | 低风险：best-effort |
| 凭据 create / update / delete | `credential.create/update/delete` | actor tenant | 仅 provider、掩码指纹，不含 Key | **高风险：outbox** |
| 数据删除（数据源/报告/原始数据） | `data.delete` | resource tenant | `resource_type` 区分；before 快照 + 级联计数 | **高风险：outbox** |
| 报告生成 | `report.generate` | report tenant | report_id / format / status | 低风险：best-effort |
| 报告下载 | `report.download` | report tenant | report_id / format | 低风险：best-effort |
| 数据导出 | `data.export` | resource tenant | export_type / row_count / format | **高风险：outbox** |
| 任务取消 / 重试 | `task.cancel/retry` | task tenant | 状态前后 | 低风险：best-effort |
| 租户状态变更（platform_admin） | `tenant.status.change` | target tenant | status before/after | **高风险：outbox** |
| stale Run 回收（系统事件） | `run.recovered_stale` | run tenant | run_id / task_id / old_status | **高风险：outbox** |

> 高风险事件不能“业务成功、审计缺失”；低风险事件允许主流程继续，但必须告警。
> 导出/对比需要写 `data.export`；其他纯读操作不默认写审计，避免日志膨胀。

### 4.3 append-only（P1-3 已定：DB trigger）

**机制**：在 `audit_logs` 上创建 `BEFORE UPDATE OR DELETE` trigger，函数直接 `RAISE EXCEPTION 'audit_logs is append-only'`；应用层只保留 `INSERT` / `SELECT`，不提供 update/delete API。

| 关注点 | 规则 |
|---|---|
| 运行时绕过 | 无；应用层不提供 UPDATE/DELETE 路径，DB trigger 强制拒绝 |
| migration / 数据修复 | DDL 不受 trigger 影响；如必须改历史行，只能在单独评审的 migration 中 `ALTER TABLE audit_logs DISABLE TRIGGER trg_audit_logs_append_only`，改完同一事务 `ENABLE`；禁止临时手工绕过 |
| 备份 / 恢复 | `pg_dump` / restore 以 INSERT 方式重建；不触发 UPDATE/DELETE；恢复演练需验证 trigger 仍在 |
| 审计导出 | 只读 `SELECT`；导出为 CSV/JSON，不修改原表；导出动作本身记 `data.export` |
| 分区 / 归档 | 不在 PR-4；未来分区 drop 属单独批准的维护操作，禁止用 DELETE 做 retention |
| 写入失败 | 按事件分级：高风险走 durable outbox；低风险才允许 savepoint best-effort + 告警。详见 4.5 |
| 历史行 | 不回填 `before/after`；新增事件必须带 tenant_id（可识别时） |

测试（PR-4b）：

- 直接 SQL `UPDATE audit_logs` / `DELETE` → 异常；
- 正常 `INSERT` 成功；
- migration up/down 后 trigger 仍存在；
- 低风险 audit insert 失败时业务事务不回滚（savepoint），且产生告警日志；高风险按 4.5 走 outbox。

### 4.4 脱敏

- 白名单序列化：只记录名称、状态、类型、计数、provider、掩码指纹。
- 禁止记录：API Key、Authorization、Cookie、密码、完整 prompt/response（除非已有单独脱敏策略）。
- 测试：构造含 `api_key` / `password` / `authorization` / `cookie` 的 payload，断言审计中不出现原值。

### 4.5 审计失败分级与 durable outbox（P1 已定）

**不允许所有事件统一 best-effort。** 按事件风险分两级：

| 等级 | 事件 | 失败策略 | 失败后果 |
|---|---|---|---|
| 高风险 | `tenant.cross_access`、`credential.*`、`data.delete`、`data.export`、`tenant.status.change`、`run.recovered_stale` | 业务事务内写 `audit_outbox`（durable），由 dispatcher 异步投递 `audit_logs` | outbox 写入失败 → 业务事务回滚 / 任务重试；audit_logs 投递失败 → outbox 保留 + 重试 + 告警，不丢失 |
| 低风险 | `login.success/failure`、`token.revoke`、`report.generate/download`、`task.cancel/retry` | savepoint 内直接写 `audit_logs`；失败回滚 savepoint | 主流程继续；写 `audit_write_failed` 告警指标 |

#### 4.5.1 高风险流程

1. 业务事务内 `INSERT audit_outbox`（与业务行同一事务，`flush` 参与提交）；
2. outbox 插入失败 → 抛出业务异常 / 回滚事务；API 返回 5xx，Celery 任务异常并按策略重试，**不允许业务成功但审计缺失**；
3. 事务提交后由 dispatcher 读取 `status='pending'` 行，写 `audit_logs` 并标记 `delivered`；
   - 写 `audit_logs` 使用 `INSERT ... ON CONFLICT (event_id) DO NOTHING`；
   - 若 `audit_logs` 已存在同 `event_id`，直接标记 outbox `delivered`，不产生重复审计；
4. `audit_logs` 写入失败 → outbox 行保留、指数退避重试、`audit_outbox_pending` 告警；不删除 outbox；
5. `run.recovered_stale` 与 Run/Task 状态更新同事务写 outbox；outbox 失败则回滚更新，Run 保持 stale，下轮重试。

#### 4.5.2 低风险流程

1. `SAVEPOINT` 内写 `audit_logs`；
2. 插入失败 → 回滚 savepoint，记录 error log + `audit_write_failed` 指标；
3. 业务主流程继续，不返回失败。

#### 4.5.3 outbox 表（026）

| 字段 | 说明 |
|---|---|
| `id` BIGSERIAL | 主键 |
| `event_id` UUID unique | 幂等键；与 `audit_logs.event_id` 对应 |
| `tenant_id` / `user_id` | 事件归属；平台级可为 NULL |
| `action` / `resource_type` / `resource_id` | 与 audit_logs 对齐 |
| `before` / `after` / `details` / `request_id` | 安全快照；同一脱敏白名单 |
| `ip_address` / `user_agent` | 与 audit_logs 对齐 |
| `status` | `pending` / `delivered` |
| `attempts` / `next_attempt_at` | 重试控制 |
| `created_at` / `delivered_at` | 时间戳 |

- outbox 行可更新状态（不是 append-only 表）；`audit_logs` 仍是 append-only trigger。
- outbox 不存密钥；脱敏规则与 audit_logs 相同。
- dispatcher：每 5s 批量 100 条；失败退避 5s/30s/5min；`pending > 5min` 或 `attempts > 5` 告警。
- **保留/清理**：`delivered` 行保留 **30 天**后由日任务清理；`pending` **永不自动清理**；`audit_logs` 保留 **730 天**（策略，PR-4 不实现 audit_logs purge）。
- 清理任务只 `DELETE audit_outbox WHERE status='delivered' AND delivered_at < now()-30d`；不碰 pending。
- 清理动作自身写低风险审计 `audit.cleanup`（best-effort + `audit_write_failed` 告警）。

#### 4.5.4 只读高风险事件的事务边界（P1 已定）

`tenant.cross_access`、`data.export` 等读请求没有业务写事务，不能依赖请求结束时的 `get_db` 提交：

1. 在返回数据之前，用**独立短事务** `SessionLocal()` 插入 `audit_outbox` 并 `commit`；
2. outbox 写失败 → **拒绝请求**（503 / deny），不得返回数据；
3. 成功后继续查询/生成导出；审计已 durable，不依赖响应阶段提交；
4. 同一请求重试时用新的 `event_id`；同一事件重试由 outbox/dispatcher 幂等键去重。

测试：模拟短事务 outbox 失败 → 跨租户读/导出返回 503 且无数据；成功 → 响应前 outbox 已存在。

#### 4.5.5 测试（PR-4b）

| 用例 | 预期 |
|---|---|
| 高风险事件 outbox 插入失败 | 业务请求失败/事务回滚，业务行不存在 |
| 高风险事件 outbox 成功、audit_logs 插入失败 | outbox 保持 pending；重试后 audit_logs 有记录；无丢失 |
| 同一 outbox 投递两次 | `audit_logs` 只有一条（`event_id` 唯一 + `ON CONFLICT`） |
| 只读跨租户 outbox 失败 | 返回 503 / deny，无跨租户数据 |
| `run.recovered_stale` outbox 失败 | Run/Task 更新回滚，Run 仍 stale；下轮重试 |
| 低风险事件 audit_logs 插入失败 | 主流程成功；产生 `audit_write_failed` 告警 |
| 低风险事件正常 | audit_logs 有记录 |
| outbox 清理 | delivered 超 30 天删除；pending 保留；audit_logs 不受影响 |
| 所有事件 | 无“静默丢失”：outbox 深度/失败指标可查 |

### 4.6 认证事件等级（可选复核）

`login.failure` / `token.revoke` 当前保持**低风险 best-effort**（主流程不因审计失败中断）。
如后续合规要求“认证事件不可丢”，在 M4-A 数据权利/审计评审时升级为高风险 outbox；
升级不改变本 scope 的其他设计。

## 5. staging 验证步骤（PR-4 部分）

> 前提：PR-3 staging 025 已通过；PR-4 代码另行部署到 staging。

| # | 验证 | 预期 |
|---|---|---|
| 1 | 凭据 create/update/delete | `audit_logs.tenant_id` 为 actor tenant；无 Key 明文 |
| 2 | 数据删除 | `data.delete` 审计 before/after 含名称/类型/级联计数 |
| 3 | 任务取消/重试 | 审计状态前后正确 |
| 4 | 报告生成 / 下载 | `report.generate` / `report.download` 均带 report tenant |
| 5 | 登录成功/失败 + token 撤销 | `login.success/failure`、`token.revoke` 均写审计；失败不泄露密码 |
| 6 | 数据导出 | `data.export` 带 resource tenant / row_count |
| 7 | `recover_stale_rag_runs` | A/B 各有 stale Run；flag=true 下各自恢复，跨租户更新 = 0；无 context 失败 |
| 8 | digest / cost monitor | 不写业务表；日志 `scope=platform` |
| 9 | append-only | UPDATE/DELETE 被 trigger 拒绝；导出只读 |
| 10 | 跨租户 | 既有 404 矩阵不回归 |

## 6. 拆分建议（均需单独批准）

| 子项 | 内容 | 是否含 migration |
|---|---|---|
| PR-4a | 后台任务 context 覆盖 + recover_stale 显式 context/tenant 谓词 + A/B 测试 | 否 |
| PR-4b | audit before/after/request_id + trigger append-only + 事件接入 + 脱敏 + 测试 | 是（026，暂定编号） |
| PR-4c | staging 验证记录（含 stale recovery + audit）+ 回滚/监控补充 | 否 |

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
- `recover_stale_rag_runs` A/B 测试通过：只更新对应 tenant，跨租户 0，缺 context 不失败；
- audit 事件 P1 集齐（登录/token/报告/导出/删除/租户状态/跨租户/凭据/任务/stale）；
- audit 事件带 tenant_id（可识别时），before/after 可查询且脱敏；
- 高风险事件 outbox 失败会阻塞业务；低风险事件失败不阻塞但告警；无静默丢失；
- `event_id` 幂等：同一 outbox 重试不产生重复 audit_logs；
- 只读高风险事件（跨租户/导出）在返回数据前完成 outbox 提交，失败拒绝请求；
- outbox delivered 保留 30 天、pending 不清、audit_logs 730 天策略明确；
- append-only trigger 有可执行测试；migration/备份/导出规则明确；
- staging 验证 1–10 通过并留证据；
- 不碰生产；不改变 PR-3 staging 门槛。

## 9. 实施参数（不阻塞 scope）

1. `request_id` 生成方式（请求中间件 / Celery task id）。
2. 审计导出格式与存放位置（CSV/JSON；对象存储或受控下载）。
3. `data.export` 的首批接入路由清单（对比导出、报告导出等）。

> 以上在 PR-4b 实施评审时定；append-only 机制、stale recovery 语义、P1 事件集已定，不再留待评审。
