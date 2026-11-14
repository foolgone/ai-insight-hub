# 数据库设计

> Phase 1：迁移 `019_qa_datasets`（`b2f7c1d9e4a3`）
> Phase 2：迁移 `020_rag_traces`（`c9d2a4f7b1e6`）
> 原则：**只新增表，不改既有表**；旧链路（对话清洗/质量评估）零影响。
> `rag_eval_results` 推迟到 Phase 3（与指标写入方一起建表，避免空表）。

---

## 1. 实体关系

```
users 1─n qa_datasets 1─n qa_dataset_versions 1─n qa_dataset_items
```

- 一个用户可以有多份数据集（`(user_id, name)` 唯一）；
- 一个数据集有多个版本（`(dataset_id, version)` 唯一，版本号从 1 递增）；
- 条目挂在版本下（`(version_id, item_key)` 唯一）；
- 发布后的版本不可改，修改 = 新版本（copy-on-write）。

---

## 2. 表定义

### 2.1 `qa_datasets`

| 列 | 类型 | 约束/默认 | 说明 |
|---|---|---|---|
| id | uuid | PK, `gen_random_uuid()` | |
| user_id | uuid | FK `users.id` CASCADE | 归属 |
| name | varchar(200) | NOT NULL | 数据集名 |
| description | text | | |
| source_type | varchar(20) | CHECK `doc/conv/mixed`，默认 `mixed` | 与 Q3 的 doc/conv 拆分对应 |
| created_at / updated_at | timestamp | now() | |

索引：
- `uk_qa_datasets_user_name (user_id, name) UNIQUE`
- `idx_qa_datasets_user_created (user_id, created_at)`

### 2.2 `qa_dataset_versions`

| 列 | 类型 | 约束/默认 | 说明 |
|---|---|---|---|
| id | uuid | PK | |
| dataset_id | uuid | FK `qa_datasets.id` CASCADE | |
| version | int | NOT NULL | 1,2,3… |
| status | varchar(20) | CHECK `draft/published/archived`，默认 `draft` | 状态机 |
| item_count | int | 默认 0 | 冗余计数（导入/删除后重算） |
| checksum | varchar(64) | | 发布时计算的 sha256 |
| note | text | | 版本说明 |
| published_at | timestamp | | |
| created_at | timestamp | now() | |

索引：
- `uk_qa_dataset_versions_dataset_version (dataset_id, version) UNIQUE`
- `idx_qa_dataset_versions_dataset_status (dataset_id, status)`

### 2.3 `qa_dataset_items`

| 列 | 类型 | 约束/默认 | 说明 |
|---|---|---|---|
| id | uuid | PK | |
| version_id | uuid | FK `qa_dataset_versions.id` CASCADE | |
| item_key | varchar(80) | NOT NULL | 稳定外部键（`CONV-10215` / `Q001`） |
| query | text | NOT NULL | 用户问题 |
| gold_answer | text | | 标准答案（纯检索集可为空） |
| gold_evidence | jsonb | 默认 `[]` | `[{document_id, chunk_id, evidence_text, page_number, metadata}]` |
| category | varchar(100) | | 业务分类 |
| difficulty | varchar(20) | | 难度 |
| source | varchar(50) | | `doc:robot-backend` / `conv:knowledge` |
| split | varchar(10) | CHECK `train/valid/test`，默认 `test` | |
| metadata | jsonb | 默认 `{}` | 原始字段快照（session_id、llm 预筛分等） |
| created_at | timestamp | now() | |

索引：
- `uk_qa_dataset_items_version_key (version_id, item_key) UNIQUE`
- `idx_qa_dataset_items_version_split (version_id, split)`
- `idx_qa_dataset_items_version_category (version_id, category)`

> 列名 `metadata` 与 SQLAlchemy Declarative 的保留属性冲突，ORM 属性名用 `item_metadata`，
> API 与 DB 列名仍为 `metadata`。

---

## 3. 关键规则（服务层实现，非 DB 约束）

| 规则 | 实现位置 | 说明 |
|---|---|---|
| 发布后不可变 | `qa_dataset_service._ensure_draft` | PATCH/DELETE/import 前校验，违反 → 409 `QA_DATASET_IMMUTABLE` |
| 导入全量校验 | `validate_import_payload` + `import_items` | 先收集全部错误；有错 → 400，**一条都不写** |
| checksum | `compute_checksum` | 见下节 |
| 计数 | `item_count` | 导入/删除后 `count_items` 重算，不做触发器 |
| 重名 | `create_dataset` / `update_dataset` | 409 `QA_DATASET_NAME_EXISTS` |

### checksum 的计算范围与稳定序列化

- **范围**：`item_key / query / gold_answer / gold_evidence / category / difficulty / source / split / metadata`（不含 id、created_at）；
- **排序**：条目按 `item_key` 升序；证据按 `(document_id, chunk_id, evidence_text, page_number)` 升序；
- **序列化**：`json.dumps(ensure_ascii=False, sort_keys=True, separators=(",", ":"))`；
- **哈希**：UTF-8 编码后 `sha256`，64 位十六进制。

因此：条目顺序、证据顺序变化不影响 checksum；任何内容变化都会改变。

---

## 4. 迁移与回滚

```bash
# 升级
alembic upgrade head          # 9a4d2f8c6e15 -> b2f7c1d9e4a3

# 回滚（只删 3 张新表，不动旧表）
alembic downgrade 9a4d2f8c6e15

# 漂移检查
alembic check                 # No new upgrade operations detected
```

执行记录（2026-11-13）：

```
current: 9a4d2f8c6e15  ->  b2f7c1d9e4a3 (head)
alembic check: No new upgrade operations detected
```

---

## 5. 未做（有意为之）

| 项 | 原因 |
|---|---|
| `dataset_item.evidence` 单独建表 | Phase 1 用 JSONB 快照足够；拆表会引入 join 与生命周期问题 |
| `analysis_results` 复用 | 语义绑定 `cleaned_data`，混用会污染对话评测 |
| DB 触发器保证不可变 | 规则需可测试、可回滚；服务层 + 测试已覆盖 |
| 软删除 / 归档版本 | Phase 1 未提供删除数据集接口，避免误删；archive 状态字段已预留 |

---

## 6. Phase 2 增量（迁移 020：`rag_traces`）

```
qa_dataset_items 1─n rag_traces        （dataset_item_id，ON DELETE SET NULL）
tasks            1─n rag_traces        （task_id，Phase 3 评测任务用）
users            1─n rag_traces        （user_id，CASCADE）
```

| 列 | 类型 | 说明 |
|---|---|---|
| id | uuid | PK（对外叫 `trace_id`） |
| user_id | uuid | FK users CASCADE |
| dataset_item_id | uuid | FK qa_dataset_items SET NULL |
| task_id | uuid | FK tasks SET NULL |
| idempotency_key | varchar(120) | **唯一**；Phase 3 用 `task:{id}:item:{id}` 保证不重复执行 |
| adapter | varchar(50) | `mock` / `weknora` |
| mode | varchar(20) | CHECK `retrieve` / `query` |
| context_source | varchar(20) | CHECK `hybrid_search` / `agent_chat` / `none` |
| external_session_id | varchar(100) | WeKnora session id |
| query / answer | text | 问题 / 最终回答（检索模式 answer 为空） |
| retrieved_contexts | jsonb | `[{document_id, chunk_id, title, content, score, rank, metadata}]` |
| raw_response | jsonb | 外部原始响应（超 200k 字符截断并标记） |
| model_config / retrieval_config / prompt_snapshot | jsonb | 配置快照 |
| latency_ms | int | 实测耗时（不伪造） |
| token_usage | jsonb | 外部未提供则为 NULL |
| missing | jsonb | 缺失字段名数组（区分「缺失」与「0」） |
| status | varchar(20) | CHECK `success` / `failed` |
| error_message | text | 失败原文（截断 2000 字） |

索引：`uk_rag_traces_idempotency_key`（唯一）、`(user_id, created_at)`、`(task_id, status)`、`dataset_item_id`。

### 未建的表现在建（有意为之）

| 表 | 原因 |
|---|---|
| `rag_eval_results` | Phase 2 没有指标写入方；建表即空表。Phase 3 与指标一起落 |
| `experiments` / `experiment_runs` | Phase 4 才使用 |

### 迁移执行记录（2026-11-13）

```
alembic current : b2f7c1d9e4a3 -> c9d2a4f7b1e6 (head)
alembic check   : No new upgrade operations detected
```

> 开发库（VM `aiinsight-postgres:5433`）中，本阶段曾提前创建的 `rag_eval_results`（0 行）
> 已手工 DROP；生产库（`aiinsight-prod-postgres`）未做任何变更。

---

## 7. Phase 3 增量（迁移 021：`rag_evaluation_runs` / `rag_evaluation_results`）

revision=`d4e8b1c6f902`，down_revision=`c9d2a4f7b1e6`。

### 7.1 `rag_evaluation_runs`

| 列 | 类型 | 说明 |
|---|---|---|
| id | uuid | PK（对外 `run_id`） |
| user_id | uuid | FK users CASCADE |
| task_id | uuid | FK tasks SET NULL，**唯一**（1 task : 1 run） |
| parent_run_id | uuid | FK 自关联 SET NULL（重试链） |
| attempt / retry_scope | int / varchar(20) | `1..`；CHECK `all` / `failed_only` |
| dataset_id | uuid | FK qa_datasets SET NULL（快照名仍在） |
| dataset_name | varchar(200) | 创建时快照，数据集改名不影响历史 |
| dataset_version_id | uuid | FK qa_dataset_versions **RESTRICT** |
| dataset_checksum | varchar(64) | 执行前比对，篡改 → `failed(dataset_modified)` |
| execution_mode | varchar(20) | CHECK `retrieve` / `query` |
| adapter | varchar(50) | `mock` / `weknora` |
| retrieval_config | jsonb | `{top_k, precision_mode, split}`（连 trace 复用比对） |
| judge_config | jsonb | `{model, temperature, prompt_version, metric_versions}` |
| config_snapshot | jsonb | 完整配置快照（含指标清单与版本） |
| item_selection | jsonb | `{mode, split?, parent_run_id?, item_ids}` |
| total/completed/skipped/failed_items | int | 计数（completed 含全 skipped 条目） |
| status | varchar(20) | CHECK `pending/running/completed/partial_failed/failed/cancelled` |
| aggregate | jsonb | 收尾生成的聚合（指标 mean/coverage/skip_reasons） |
| error_message | text | `dataset_modified` / `time_budget_exhausted` / `stale_worker` 等 |
| started_at / completed_at / last_heartbeat_at | datetime | 心跳供 stale 回收 |
| created_at | datetime | 默认 now() |

索引：`uk_rag_evaluation_runs_task_id`（唯一）、`(user_id, created_at)`、
`(dataset_version_id)`、`(status)`、`(parent_run_id)`。

### 7.2 `rag_evaluation_results`

| 列 | 类型 | 说明 |
|---|---|---|
| id | uuid | PK |
| run_id | uuid | FK runs CASCADE |
| dataset_item_id | uuid | FK qa_dataset_items **RESTRICT** |
| trace_id | uuid | FK rag_traces SET NULL（重试复用父 Trace 时指向父 Trace） |
| metric_name | varchar(40) | 指标名 |
| metric_version | varchar(20) | 指标版本（不覆盖历史） |
| status | varchar(20) | CHECK `evaluated` / `skipped` / `failed` |
| score | float | `skipped` / `failed` 为 NULL（**不补 0**） |
| skipped_reason | varchar(60) | `gold_evidence_missing` / `answer_missing` 等 |
| details / judge_config | jsonb | 指标细节 / Judge 配置快照 |
| raw_output / raw_truncated | text / bool | Judge 原文（20k 截断） |
| latency_ms | int | Judge 或单条耗时 |
| error_message | text | 失败原文（截断 2000） |
| created_at | datetime | 默认 now() |

索引：**唯一** `(run_id, dataset_item_id, metric_name, metric_version)`（幂等/重投递安全）、
`(run_id, metric_name, status)`、`(run_id, status)`、`(trace_id)`。

### 7.3 `tasks.task_type` CHECK

由 6 种扩到 7 种，加入 `rag_eval`；**不动** `tasks.status` 枚举（`partial_failed` 只存在于 run）。
回滚会先删两张新表，再 `DELETE FROM tasks WHERE task_type='rag_eval'` 后恢复旧 CHECK。

命名规范提醒：约束实际名带前缀（`ck_tasks_task_type_valid`），
`op.drop_constraint` 传**未加前缀**的 `task_type_valid`。

### 7.4 迁移执行记录（2026-11-14，开发库）

```
alembic current : c9d2a4f7b1e6 -> d4e8b1c6f902 (head)
alembic check   : No new upgrade operations detected
```

生产库仍为 `9a4d2f8c6e15`（018）；上线需按 019 → 020 → 021 顺序执行。
