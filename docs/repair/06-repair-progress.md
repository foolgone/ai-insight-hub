# 修复进度（按 Phase 记录）

> 每阶段完成后追加：改动文件、迁移、测试结果、遗留问题。
> 上一阶段：`docs/repair/01-implementation-plan.md`

---

## Phase 1 · 数据基础（数据集 / 版本 / 条目）— 已完成

**日期**：2026-11-13
**范围**：只新增 RAG 评测数据集链路；未改动对话清洗/质量评估/知识库任何代码路径。

### 1. 改动文件

| 类型 | 文件 | 说明 |
|---|---|---|
| 新增 | `backend/app/models/qa_dataset.py` | 3 个 ORM：`QaDataset` / `QaDatasetVersion` / `QaDatasetItem` |
| 新增 | `backend/app/repositories/qa_dataset.py` | 纯 SQL：数据集/版本/条目读写、计数、过滤 |
| 新增 | `backend/app/schemas/qa_dataset.py` | 请求/响应 Schema + 导入错误结构 |
| 新增 | `backend/app/services/qa_dataset_service.py` | 归属、状态机、导入校验、checksum、统计 |
| 新增 | `backend/app/api/v1/qa_datasets.py` | 13 个端点 |
| 新增 | `backend/migrations/versions/20261113_2200_b2f7c1d9e4a3_019_qa_datasets.py` | 迁移 019 |
| 新增 | `backend/tests/unit/test_qa_dataset_rules.py` | 12 条（checksum + 导入校验） |
| 新增 | `backend/tests/integration/test_qa_dataset_api.py` | 11 条（CRUD/发布/不可变/权限/回滚/样例导入） |
| 新增 | `backend/tests/fixtures/qa_dataset_sample.json` | 20 条脱敏样例（10 文档 + 10 对话） |
| 修改 | `backend/app/models/__init__.py` | 登记 3 个新模型（Alembic 依赖） |
| 修改 | `backend/app/api/v1/__init__.py` | 挂载 `/qa-datasets` |
| 修改 | `backend/app/core/errors.py` | 新增 4 个错误码 + 状态映射 |
| 修改 | `backend/app/core/exceptions.py` | 新增 4 个异常 |
| 修改 | `backend/tests/unit/test_errors.py` | 错误码契约 34 → 38 |
| 修改 | `backend/tests/unit/test_models_schema.py` | 表契约 18 → 21 + 新表列断言 |
| 修改 | `backend/tests/integration/test_openapi.py` | 契约加入 8 条新路径 |
| 修改 | `frontend/src/lib/errorMessages.js` | 4 个错误码中文文案 |
| 新增 | `docs/repair/02-database-design.md` | 表结构 / checksum 规则 / 迁移回滚 |
| 新增 | `docs/repair/03-api-design.md` | 13 个端点 / 请求响应 / 行为约定 |

### 2. 数据库迁移

```
019_qa_datasets  revision=b2f7c1d9e4a3  down_revision=9a4d2f8c6e15
新增：qa_datasets / qa_dataset_versions / qa_dataset_items
索引：3 个唯一索引 + 5 个普通索引
```

执行记录：

```
alembic current : 9a4d2f8c6e15 -> b2f7c1d9e4a3 (head)
alembic check   : No new upgrade operations detected
```

回滚：`alembic downgrade 9a4d2f8c6e15`（只删 3 张新表）。

### 3. 关键实现

| 要求 | 实现 | 证据 |
|---|---|---|
| 发布后不可变 | `_ensure_draft()`，PATCH/DELETE/import 前校验 → 409 | `test_publish_then_immutable` |
| 修改产生新版本 | `create_version(from_version_id=...)` 逐条复制（copy-on-write） | `test_new_version_copy_is_isolated` |
| 导入全量校验 + 回滚 | `validate_import_payload` 先收集错误，有错即 400 且不写库 | `test_import_rejects_bad_rows_with_index_and_rolls_back` |
| 错误行号 | `errors[].index` 为 1-based 行号；字段名转 snake_case | `test_validate_import_requires_evidence_text` |
| 证据不得只有 ID | `GoldEvidence.evidence_text` 必填且 ≥10 字 | 同上 + `test_import_sample_fixture` |
| checksum 范围稳定 | 9 字段、条目按 `item_key`、证据按四元组排序、紧凑 JSON | `test_checksum_is_stable_across_item_and_evidence_order` |
| 两类数据独立 | `source_type ∈ doc/conv/mixed`，独立数据集 | `test_create_list_and_detail` |
| 权限 | 读三角色 / 写 admin+user / 归属 admin 全通 | `test_permissions` |

### 4. 测试结果

| 项 | 结果 |
|---|---|
| 新增单测 | 12 passed |
| 新增集成 | 11 passed |
| 后端全量 | **760 passed**（Phase 0 基线 730，净增 30：新增测试 23 + 表列参数化 3 + 异常映射参数化 4；无删除） |
| mypy | `Success: no issues found in 148 source files` |
| black / flake8 | 通过（264 文件 unchanged / 0 error） |
| lint-imports | `5 kept, 0 broken` |
| 前端 | 77 文件全绿；行 95.58% / 分支 83.36% / 函数 81.26% |
| 迁移漂移 | `alembic check` 无差异；`downgrade 9a4d2f8c6e15 → upgrade head` 往返成功 |

### 5. 与 Phase 0 方案的差异

| 项 | 方案 | 实际 | 原因 |
|---|---|---|---|
| 错误码 | 3 个（NOT_FOUND / IMMUTABLE / IMPORT_INVALID） | **4 个**（多 `QA_DATASET_NAME_EXISTS`） | 重名是 409 冲突，不应复用 400 的「导入校验失败」 |
| 端点 | 11 个（数据集 11） | **13 个**（多 `GET /versions`、`GET /items/{id}`） | 验收要求「查询单条样本」；版本列表从详情拆出便于前端 |
| 删除数据集 | 未列 | 未实现 | Phase 1 验收不含删除；避免误删不可逆（Q6 决策） |
| `source_type` | `doc/conv/mixed` | 同 | — |

### 6. 已知限制

1. **无删除/归档数据集接口**：避免误删；`qa_dataset_versions.status=archived` 已预留；
2. **单条导入上限 2000**：459 条可一次导入；更大数据集需分批；
3. **并发导入同一 `item_key`**：依赖唯一索引，捕获 `IntegrityError` 返回 400（提示重试），非静默覆盖；
4. **`metadata` 列名与 ORM 属性**：DB 列名为 `metadata`，ORM 属性为 `item_metadata`（SQLAlchemy 保留字），API 输出仍为 `metadata`；
5. **前端页面未做**：数据集管理页在 Phase 6；本阶段只保证 API 与错误文案可用；
6. **未接入 459 条真实数据**：需要业务授权后通过导入接口写入（本阶段只提供 20 条脱敏样例）。

### 7. 下一阶段（Phase 2）准备

- 需要：WeKnora 的 `BASE_URL / API_KEY / AGENT_ID / KB_ID / TENANT_ID`（Q1 决策：先用 Mock，接口契约按外部脚本实现）；
- 迁移 020：`rag_traces` / `rag_eval_results` / `experiments` / `experiment_runs`；
- 验收：Mock 下跑通「建 trace → 查 trace」，真实联调视凭据。
