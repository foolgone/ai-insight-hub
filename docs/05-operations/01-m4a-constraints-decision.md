# M4-A 约束决策文档（租户 / 保留期 / 审计 / 告警 / 成本 / 数据权利）

> 状态：`accepted_baseline`（决策基线；**不是 implementation approved**）；**只写文档，不写代码、不做 migration、不碰生产。**
> 日期：2026-11-24（2026-11-25 补 5 个实现前 P1）
> 适用范围：AI Insight Hub 平台化前的约束设计。
> 上游：M2 P0 accepted；M3 P0 accepted（页面/流程）；Judge v1.2.5 beta/inactive。

## 0. 结论摘要

| 主题 | 当前状态 | 主要缺口 | 推荐方向 |
|---|---|---|---|
| 租户 | 单工作区，资源按 `user_id` 隔离；admin 全通 | 无 tenant/org 表；admin 可跨用户；无租户配额 | 引入 `tenant_id`，admin 降为 tenant_admin，另设 platform_admin |
| 保留期 | 无统一 TTL/清理；报告有 `expires_at` 但无清理任务 | 对话/音频/Trace/评测结果无期限；文件可能残留 | 按数据类默认 TTL + 每日 purge + 审计 |
| 审计 | `audit_logs` 表存在，仅凭据变更写入 | 评测/配置/导出/删除未审计；无 tenant_id、无前后值 | 全写操作审计，append-only，保留 730 天 |
| 告警 | Prometheus 抓取 + Grafana 概览；无 alert rules | 无 Alertmanager；失败/invalid/队列/成本无自动告警 | 规则化告警 + 飞书/邮件，P1/P2 分级 |
| 成本 | `llm_calls` 记录 token/成本；日限额用于降级 | 月限额未执行；价格默认 0；无租户预算 | 租户/用户配额，月度硬停，成本看板 |
| 数据权利 | 报告下载、数据源删除；报告删除只删 DB 行 | 无账号/租户导出删除；无脱敏/跨境策略 | 导出、删除、脱敏、驻留四件事产品化 |

原则：**先定约束，再改 schema；不在本文件内实现。**

## 1. 租户（Tenant）

### 1.1 当前状态

- `users.role` 只有 `admin / user / viewer`（`backend/app/models/user.py`）。
- 业务表普遍有 `user_id`：`data_sources`、`rag_traces`、`rag_evaluation_runs/results`、`qa_datasets`、`reports`、`llm_calls` 等。
- 归属校验 `assert_owner`：**admin 直接放行**，其余必须 `user_id == current_user.id`（`backend/app/core/ownership.py`）。
- 没有 `tenants / organizations / workspaces` 表；`WEKNORA_TENANT_ID` 只是外部 RAG 的租户，不是平台租户。

### 1.2 缺口

1. admin 能看到所有用户的数据，无法做“客户 A 的管理员只看 A”。
2. 没有租户级配额（数据源、并发、成本、存储）。
3. 查询以 `user_id` 为边界，跨用户共享（团队）没有模型。
4. 审计、告警、成本都无法按租户聚合。

### 1.3 选项

| 选项 | 说明 | 适用 |
|---|---|---|
| A. 保持 user 级 | 不引入 tenant；admin 全通 | 单客户私有部署 |
| B. tenant + tenant_admin（推荐） | `tenants` 表；`users.tenant_id`；业务表补 `tenant_id`；admin→tenant_admin；platform_admin 单独 | SaaS / 多客户 |
| C. 外部 IdP/Org 映射 | 用外部组织作为租户，平台只存 org_id | 已有企业身份系统 |

### 1.4 推荐

- 采用 **B**：`tenants(id, name, status, plan, created_at)`；`users.tenant_id NOT NULL`；所有 owner 表补 `tenant_id`（先回填单一默认租户）。
- 角色：`platform_admin`（跨租户运维）、`tenant_admin`（本租户全权）、`user`、`viewer`。
- 所有 repository 查询强制 `tenant_id` 过滤；`assert_owner` 改为 `assert_tenant_access`。
- 存储 key 前缀 `tenant/<id>/...`；成本、审计、告警均带 `tenant_id`。

### 1.5 风险

- 迁移期跨租户泄漏（必须双写/回填/校验）；
- 现有 admin 账号权限需要重新分配；
- 外部 WeKnora tenant 与平台 tenant 的映射需明确。

## 2. 保留期（Retention）

### 2.1 当前状态

- 没有统一 retention 配置或清理任务。
- `reports.expires_at` 在生成时设为 30 天（`report_service.py:560`），但没有 purge job。
- 数据源支持软删（`deleted_at`）与 force 物理删；`_RELATED_MODELS` 只统计 RawData/CleanedData/AnalysisResult/KnowledgeBase/Report/Task，**不含 RagTrace/RagEvaluationRun**。
- 报告删除只 `session.delete(report)`，未删除对象存储文件（`report_service.delete_report`）。
- `llm_calls` 长期保留，用于成本与审计。

### 2.2 推荐默认值（可按租户覆盖）

| 数据类 | 默认保留 | 说明 |
|---|---|---|
| 原始上传（对话/音频） | 90 天 | 可配置 30/90/180 |
| 清洗后数据 | 180 天 | 与原始数据联动 |
| RagTrace | 180 天 | 含 question/answer/contexts |
| 评测 Run/Result 元数据 | 365 天 | 指标与历史记录保留；不因报告文件过期而删除 |
| 报告文件 | 30 天 | 已有 `expires_at`；过期可重新生成 |
| 报告元数据 | 365 天 | 与评测 Run 对齐；删文件不删历史指标 |
| `llm_calls` | 400 天 | 计费/成本对账 |
| `audit_logs` | 730 天 | 合规 |

### 2.3 机制

- 每日 purge job（Celery beat）：按 `expires_at`/`created_at` 删除 DB 行 + 存储对象；先 dry-run 统计，再实删；每次写审计。
- 软删 → 宽限期（如 7 天）→ 物理删。
- 租户级 `retention_policy` JSON；legal hold 可冻结。
- 删除必须可观测：purge 数量、失败、对象存储残留。

### 2.4 风险

- 误删不可恢复；需要备份/宽限期；
- 报告与评测结果的引用关系（删数据集版本会影响历史 Run）；
- 对象存储孤儿文件。

## 3. 审计（Audit）

### 3.1 当前状态

- `audit_logs` 表存在（`backend/app/models/security.py`），字段：user_id, action, resource_type, resource_id, details, ip, user_agent, created_at。
- 只有凭据变更写入（`credential_service._write_audit`）。
- `tasks` 与 `llm_calls` 提供部分执行历史，但不是合规审计。

### 3.2 缺口

- 评测创建/重试/取消、数据集发布、报告生成/删除、导出、删除账号等未审计；
- 无 tenant_id；无 before/after；无查询/导出界面；无保留期。

### 3.3 推荐

审计以下动作（最小集）：

| 类别 | 动作 |
|---|---|
| 评测 | run.create / run.retry / run.cancel |
| 数据集 | dataset.create / version.publish / item.delete |
| 报告 | report.generate / report.download / report.delete |
| 配置 | credential.update / prompt.activate / target.change |
| 数据权利 | data.export / data.delete / account.delete |
| 认证 | login.success / login.failure / token.revoke |

字段补充：`tenant_id`、`actor_role`、`request_id`、`before/after`（脱敏）、`result`。
存储：append-only；应用账号无 UPDATE/DELETE 权限；保留 730 天；导出 CSV/JSON。

### 3.4 风险

- `details` 可能含 PII，需要脱敏；
- 日志量增长，需分区/归档。

## 4. 告警（Alerting）

### 4.1 当前状态

- Prometheus 抓取 `api:8000/metrics` 与 `worker:9109/metrics`（`ops/prometheus/prometheus.yml`）。
- Grafana 概览面板：API 存活、LLM 速率/延迟、Agent、Token、成本（`ops/grafana/dashboards/aiinsight-overview.json`）。
- **没有 alert rules / Alertmanager**。
- `cost_monitor` 只在超过日限额阈值时写 warning 日志。

### 4.2 推荐规则（P1/P2）

| 告警 | 条件 | 级别 |
|---|---|---|
| API 5xx | 5 分钟 >5% | P1 |
| 队列堆积 | 待处理任务 >100 或最老 >10 分钟 | P1 |
| 评测失败率 | 15 分钟 failed/total >10% | P1 |
| invalid 激增 | 对比 7 天基线 +20pp | P2 |
| 日成本 | >80% 预警 / >100% 硬停 | P1 |
| 月成本 | >80% 预警 | P2 |
| DB/Redis | 不可用/连接池耗尽 | P1 |
| 磁盘 | >85% | P2 |

通道：Alertmanager → 飞书/邮件；告警需带 tenant_id、run_id、dashboard 链接。

### 4.3 风险

- 阈值需要基线，否则误报；
- 告警风暴需分组/抑制；
- 多租户后需按租户聚合，避免互相淹没。

## 5. 成本（Cost）

### 5.1 当前状态

- `llm_calls` 记录 input/output tokens、input/output/total cost、model、service、key_source。
- `DAILY_COST_LIMIT` 用于降级（`degradation_manager.py`）与 `cost_monitor` warning；`MONTHLY_COST_LIMIT` 配置存在但未执行。
- `LLM_PRICE_INPUT_PER_MTOK` / `OUTPUT` 默认 **0.0**，未配置时成本为 0。
- BYOK（用户自带 Key）`key_source='user'`，不计入平台日限额。
- 存储成本未核算；报告/上传文件无容量配额。

### 5.2 推荐

- 价格表：按模型维护 input/output/cache 单价；启动时校验非 0。
- 预算：租户月度预算 + 用户日预算；80% 告警、100% 硬停（Judge/清洗/报告分级）。
- 口径：平台 Key 计平台成本；BYOK 只记用量与估算成本，不进平台预算。
- 看板：按 tenant/service/model/run 聚合；月度账单导出。
- 存储：按 bucket/租户统计容量，设配额。

### 5.3 风险

- 价格变更导致历史成本不可比（需记录价格版本）；
- 硬停会影响正在运行的评测（需 graceful stop）；
- 多币种/汇率。

## 6. 数据权利（Data Rights）

### 6.1 当前状态

- 报告可下载（`/reports/{id}/download`）；数据源可软删/force 删；报告可删除（仅 DB）。
- 用户 API 只有 `GET/PATCH /users/me`、改密码；**无账号删除、无数据导出**。
- 无 PII 脱敏、无跨境/驻留配置；存储为本地或 MinIO。
- WeKnora 作为外部 RAG，数据会发送到其租户（需在 DPA 中披露）。

### 6.2 推荐

| 能力 | 设计 |
|---|---|
| 导出 | 按数据集/评测 Run/报告导出 JSON/CSV；异步任务 + 下载链接（有效期）；`question` 可能含客户数据，仅当前用户/租户可导出，禁止公开桶/链接 |
| 删除 | 账号删除（宽限 7 天）→ 级联删除业务数据 + 存储对象；租户 offboarding 同理 |
| 脱敏 | 导出前对手机号/地址/订单号做规则脱敏；原数据保留策略另定 |
| 驻留 | 明确数据存储区域（当前 VM/中国区）；跨境需单独开关与合同 |
| 披露 | 子处理者清单（WeKnora、LLM 供应商、对象存储） |

### 6.3 风险

- 删除不可逆；需要导出先行与二次确认；
- 外部 RAG 的删除/保留不受平台完全控制，需要合同约束；
- 脱敏规则不完整会泄漏 PII。

## 7. 需要决策的事项

| # | 决策 | 建议 |
|---|---|---|
| 1 | 租户模型 | B：tenant + tenant_admin + platform_admin |
| 2 | 保留期默认值 | 采用 §2.2，允许租户覆盖 |
| 3 | 审计范围与保留 | §3.3 最小集；730 天 |
| 4 | 告警阈值与通道 | §4.2；飞书优先 |
| 5 | 成本预算与硬停 | 租户月预算 + 用户日预算；100% 硬停 |
| 6 | 数据导出/删除 SLA | 导出 24h 内；删除 7 天宽限 |
| 7 | 数据驻留 | 默认中国区；跨境单独审批 |

## 8. 实施顺序（批准后，不在本文件执行）

1. 决策确认 + 目标模型冻结；
2. schema 变更设计（tenant_id 回填、audit 扩展）——单独 migration PR；
3. retention purge + 审计写入；
4. Prometheus alert rules + Alertmanager；
5. 成本预算/价格表校验；
6. 导出/删除/脱敏；
7. 租户隔离回归测试与渗透测试。

### 8.1 实现前必须补的 P1（评审结论）

1. **租户隔离验收矩阵**
   - 跨租户访问统一返回 **404**，不泄露资源存在性；
   - repository 查询强制 tenant scope，禁止只按 `user_id`；
   - 存储 key 必须为 `tenant/<id>/...`；
   - 旧数据回填默认租户，双写/校验期后再切读；
   - `platform_admin` 跨租户操作必须逐次审计。

2. **保留期拆分**
   - 报告文件 30 天；报告元数据与评测 Run **365 天**，分开写清；
   - 文件过期可重新生成，**不删除历史指标**；
   - `RagTrace` / `RagEvaluationRun` / `RagEvaluationResult` 必须进入删除级联；
   - legal hold + 7 天宽限 + dry-run 后再物理删除。

3. **审计不可篡改**
   - 应用账号对 `audit_logs` 无 UPDATE/DELETE 权限；
   - 采用 hash chain 或独立 append-only 存储；
   - before/after 必须脱敏；支持 CSV/JSON 导出。

4. **告警落地**
   - Alertmanager + 规则文件 + 飞书通道；
   - 每条告警必须有 owner、runbook、dashboard 链接；
   - 阈值先跑 **2 周观察期**，再转正式告警，避免误报。

5. **成本与数据权利**
   - 价格表启动校验非 0；记录价格版本；
   - 月预算 100% 时 **graceful stop**，不硬杀运行中任务；
   - 导出 24h SLA、删除 7 天宽限；
   - WeKnora 作为子处理者写入 DPA，明确删除/保留边界。

### 8.2 Tenant-first 实施 scope

`docs/05-operations/02-m4a-tenant-first-scope.md`：tenant 切片的表清单、迁移方案、JWT/角色、Repository/存储、feature flag、验收矩阵。状态 `scope_draft`，**尚未批准实现**；批准前不写 migration/代码。

### 8.3 P1 backlog 与当前状态

| 优先级 | 项 | 验收 | 状态 |
|---|---|---|---|
| P1-0 | Windows Celery `Event loop is closed` / asyncpg 跨 `asyncio.run` | 同一 worker 连续 3 个 Run 无 `partial_failed` | **done / verified**：`9400c82b…`、`be80f57b…`、`0352a0f8…` 全部 completed |
| P1-1 | 401 auth hydration 竞态 | 刷新/首次进入页面无 401 | **done / verified**：Playwright 登录 + reload，401=0 |
| P1-2 | 对比页 100 条结果上限/分页 | 200 条 Run 可完整对比 | **done / verified**：120 真实（每侧 5 页）+ 250 mocked；200 上限与截断提示 |
| P1-3a | 对比结果 CSV/JSON 导出 | 对比结果可导出 | **done / verified**：120 Case，noise/same_config，200 上限 mocked |
| P1-3b | 报告“Run 对比”章节 | 对比结果进入报告 | **accepted**（CI 全绿）：120 Case；复用报告模板/任务；确定性渲染；跨租户 404 |
| P1-5 | 本地测试库隔离 | 本地全量 pytest 可复现 | **done / verified**：`aiinsight_test`；连续两次 1138 passed |
| P1-4 | M4-A 实现：租户 → 审计 → 保留期 → 告警 → 成本 → 数据权利 | 按 §8 顺序拆 PR | pending（需实现批准） |

> P1-0/P1-1/P1-2/P1-3a/P1-3b/P1-5 已完成并验证；M4-A 实现仍未批准。

## 9. 边界

- 本文件只是决策文档：**不写代码、不做 migration、不碰生产、不跑 Run**。
- 不改变 M1/M2/M3 的既有验收结论。
- v1.2.5 保持 beta / inactive；不做 target/baseline/模型对比/10/40。
- M2 P0 accepted；M3 P0 accepted（页面/流程）；β 噪声提示已补。
