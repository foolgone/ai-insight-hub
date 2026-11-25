# M3 P0：两 Run 对比

> 状态：**accepted（页面/流程）**；前端只读，无新后端接口。β 噪声提示已补（P1 必补项）。**P1-2 全量分页已验收（120 Case 真实 + 250 Case mocked）**；**P1-3a CSV/JSON 导出已验收（120 Case）**；**P1-3b 报告“Run 对比”章节已验收（120 Case）**。
> 日期：2026-11-24（2026-11-25 补 P1-2 / P1-3a / P1-3b）
> 入口：`/rag-evaluations/compare?base=<runId>&target=<runId>`；Run 列表「对比 Run」、Run 详情「对比此 Run」。

## 1. 范围

| 项 | 内容 |
|---|---|
| 目标 | 同一数据集版本下，比较两个 completed Run 的指标与 Case 变化 |
| Run 选择 | 仅 completed；优先同 dataset + version |
| 指标 | F / C / R 的 base、target、delta；invalid / failed / skipped / unprocessed 分开 |
| Case diff | 按 `dataset_item_id` 对齐；`变好 / 变差 / 不变 / invalid / 未处理` |
| 钻取 | 点击 Case 跳到 M2 的 Case 详情 |
| 导出 | P1-3a 已实现 CSV/JSON（带 noise/same_config）；P1-3b 报告章节已实现 |

## 2. 实现

- 纯前端：分别调用两次 `/rag/evaluations/{id}/results`，按 item 对齐；不改 DB、不改 migration、不碰 Judge。
- 指标 delta：`target.mean - base.mean`；缺失显示 `—`，不伪装成 0。
- Case 分类：
  1. target 无结果 → `unprocessed`；
  2. target 任一指标 `invalid` → `invalid`；
  3. target 无有效分数 → `unprocessed`；
  4. 其余按 F/C/R 中**绝对变化最大**的指标判定 `improved / regressed / unchanged`，并在“说明”列标出驱动指标（如 `R -0.200`）。
- 版本不一致：页面顶部明确警告“版本不一致，Case 对齐可能不完整”，不静默比较。
- 同一 Run：提示“请选择两个不同的 Run”，不渲染表格。

## 3. 验收 Run

| 项 | Base | Target |
|---|---|---|
| Run ID | `67596d50-5782-456e-a96a-63929b9a9a80` | `56573a73-097a-400e-8b90-f7512128ab8a` |
| 数据集/版本 | M2 P0 验收数据集 / `9e7e73cb…` | 同左 |
| 状态 | completed | completed |
| 样本 | 5/5 | 5/5 |
| F | 0.700 | 0.700（Δ 0.000） |
| C | 0.120 | 0.120（Δ 0.000） |
| R | 0.540 | 0.500（**Δ -0.040**） |
| invalid / failed / skipped / unprocessed | 0 | 0 |

Case diff：**变好 1 / 变差 2 / 不变 2 / invalid 0 / 未处理 0**。

> 两条 Run 使用相同 mock 输入；F/C 稳定，R 在 3 个 Case 上出现 ±0.2 漂移。这是 Judge 评分的非确定性（beta），不是 RAG 输出变化。M3 P0 的目标是展示 diff 能力，不据此判断优化效果。

截图：`docs/04-development/assets/m3-p0/compare.jpeg`

## 4. 验收清单

| 验收项 | 结果 |
|---|---|
| 能选两个 completed Run | ✅ 下拉仅列出 completed |
| 指标 delta 正确 | ✅ R 0.540 → 0.500，Δ -0.040 |
| 至少一个 Case diff 分类正确 | ✅ 变好 1 / 变差 2 / 不变 2 |
| 点击 Case 打开详情 | ✅ 跳到 `/rag-evaluations/<run>/cases/<item>` |
| 不同 dataset/version 有警告 | ✅ 版本不一致警告（单测覆盖） |
| 无 500 / 空白页 | ✅ 页面正常渲染 |

## 4.1 β 噪声提示（P1 必补，已实现）

对比页固定展示 `JudgeNoiseNotice`：

- Judge 为 beta；同配置/同输入的两条 Run 也可能出现 ±0.2 波动；
- delta 不代表因果变化；建议重复 3 次，或确认 RAG 输入/配置确实不同，再判断优化效果；
- 同 dataset + version + adapter + mode + top_k（或配置字段不可得）时，升级为“同配置比较”强警告，明确 delta 主要反映 Judge 噪声。
- 单测覆盖：同版本同 adapter → 显示强警告；不同 adapter → 不显示强警告。

## 5. 已知问题（P1）

- ✅ 已修复（P1-0）：Windows Celery `Event loop is closed` / asyncpg 跨 `asyncio.run`；改为 worker 进程内持久 event loop，连续 3 Run 全 completed。
- ✅ 已修复（P1-2）：对比页 100 条结果上限；改按 page/limit 拉全量，200 Case 上限（见 §7）。
- ✅ P1-3a 已导出 CSV/JSON（120 Case，带 noise_notice / same_config）；P1-3b 报告章节已验收（见 §9）。
- ✅ 已修复（P1-1）：页面刷新后的 401 竞态；静默 refresh，Playwright reload 401=0。

## 6. 边界

- 不改 target、Prompt、fixture、Judge；不跑 10/40。
- 不做 pairwise 显著性、不做实验配置管理、不做自动优化。
- v1.2.5 保持 beta / inactive；F/C/R 不作 M1 证据。
- M2 P0 / M3 P0 已 accepted；P1-2 分页已验收。

## 7. P1-2：对比页全量分页（120 Case 真实验收，2026-11-25）

### 7.1 改动

| 层 | 改动 |
|---|---|
| 前端 API | `listAllRagEvaluationResults`：按 `page/limit` 串行拉完（每页 100），每侧最多 1000 行；429/502/503/504 按 `Retry-After` 退避重试（最多 3 次）。 |
| 前端 Hook | `useAllRagEvaluationResultsQuery`：对比页专用的全量结果查询，缓存键带 `maxRows`。 |
| 对比页 | 每侧最多拉 1000 行；按 `dataset_item_id` 对齐后仅展示前 200 Case；显示 `结果加载：Base loaded/total · Target loaded/total`；超过 200 显示“仅对比前 200 个 Case（对齐后共 N 个）”；加载失败展示错误与重试。 |
| 后端仓储 | `list_results` 在无显式 `sort` 时按 `dataset_item_id, metric_name` 稳定排序，保证 LIMIT/OFFSET 跨页不重复、不丢行；无 migration、无新路由。 |
| 测试 | 前端 250 Case mocked 单测（200 行上限 + 截断提示）、429 退避重试单测；后端 `test_results_pagination_is_stable`。 |

### 7.2 真实验收 Run

| 项 | Base | Target |
|---|---|---|
| Run ID | `5328123c-f3f5-4f6b-9d59-763c5e415719` | `7b2fa311-760b-4064-a45e-648647102250` |
| 数据集/版本 | M3 P1-2 分页验收数据集 / `43eccb08-4fca-43d1-87ca-974f523481be` | 同左 |
| 状态 | completed | completed |
| 样本 | 120/120 evaluated，0 failed / 0 invalid | 同左 |
| 结果行 | 480（120 × F/C/R/faithfulness_strict） | 480 |
| 分页 | 5 页（100/100/100/100/80） | 同左 |
| F | 0.776 | 0.801（Δ +0.026） |
| C | 0.128 | 0.125（Δ -0.003） |
| R | 0.498 | 0.488（Δ -0.010） |

Case diff：**变好 31 / 变差 32 / 不变 57 / invalid 0 / 未处理 0**（合计 120）。

> 两条 Run 使用相同 mock 输入与同配置；F/C/R 仍有小幅漂移，符合 Judge beta 噪声提示，不据此判断优化效果。

### 7.3 分页与对齐验收

| 验收项 | 结果 |
|---|---|
| 每侧结果完整加载 | ✅ Base 480/480、Target 480/480 |
| 每侧分页页数 | ✅ 5 页（每页 100） |
| 无重复行 | ✅ 每侧 480 loaded / 480 unique |
| 无缺行 | ✅ Base 缺于 Target 0 条；Target 缺于 Base 0 条 |
| 对齐并集 | ✅ 120（与数据集 120 items 一致） |
| UI 渲染 Case 行 | ✅ 120 |
| 截断提示 | ✅ 无（未超过 200 上限） |
| 加载中/失败状态 | ✅ `AsyncState` 加载态；失败显示错误与“重试”（两侧 refetch） |
| 429 保护 | ✅ 串行拉页 + `Retry-After` 退避，最多 3 次 |
| 首屏到 Case 表格 | ✅ 约 1.34 s（本地 dev，120 Case） |

截图：

- `docs/04-development/assets/m3-p12/compare-120.png`（指标与样本状态）
- `docs/04-development/assets/m3-p12/compare-120-cases.png`（`结果加载：Base 480/480 · Target 480/480` 与 Case 表）

### 7.4 成本降级说明（按验收规则）

- 200 Case × 3 Judge 指标 × 2 Run 的成本预计超过 **CNY 1.00**，按验收规则降级为：
  - **120 条真实 Run**（验证 2 页以上：实际每侧 5 页）；
  - **250 条 mocked 单测**（验证 200 Case 上限与截断提示）。
- 本记录不声称跑过 200 条真实 Case；200 上限由 mocked 单测覆盖。

### 7.5 测试与检查

| 项 | 结果 |
|---|---|
| 前端 250 Case 分页单测 | ✅ 200 行渲染 + “仅对比前 200 个 Case”提示 |
| 前端 429 退避单测 | ✅ 首次 429 后重试成功 |
| 前端全量测试 | ✅ 83 files / 423 tests |
| 前端 lint / build | ✅ 通过 |
| 后端 `test_results_pagination_is_stable` | ✅ 分页拼接与稳定排序一致 |
| 后端 RAG 评测集成测试 | ✅ 24 passed |

## 8. P1-3a：CSV / JSON 导出（2026-11-25）

> 范围：**仅前端导出**；不新增后端接口、不做报告注入（P1-3b）。

### 8.1 改动

| 文件 | 改动 |
|---|---|
| `frontend/src/lib/ragCompareExport.js` | 纯函数：导出 payload、CSV 转义 + BOM、文件名、Blob 下载。 |
| `frontend/src/pages/RagEvaluations/Compare.jsx` | 页头“导出 CSV / 导出 JSON”；只导出当前已对齐的 Case；无数据或加载中禁用。 |
| `frontend/src/api/ragEvaluations.js` | `listAllDatasetItems` 分页拉全量条目；修复 120 Case 中后 20 条 `item_key/question` 缺失。 |
| `frontend/src/hooks/useRagEvaluations.js` | `useAllDatasetItemsQuery`。 |

### 8.2 导出字段

- **元数据**：`schema_version`、`exported_at`、base/target run id、dataset/name/version、execution_mode、adapter、top_k、judge_model、prompt_version、`same_config`、`noise_notice`。
- **指标**：F/C/R 的 base / target / delta。
- **Case**：`dataset_item_id`、`item_key`、`question`、F/C/R base/target/delta、`verdict`、`verdict_label`、`driver_metric`、`driver_delta`、`note`。
- **汇总**：improved / regressed / unchanged / invalid / unprocessed、total、aligned_total、exported_cases、case_truncated、truncation_note。
- **上限**：只导出页面实际对比的 Case（最多 200）；超过时带截断说明。
- **文件名**：`rag-compare_<base8>_<target8>_<timestamp>.csv/json`。
- **CSV 说明**：文件开头为 `# key=value` 元数据注释块（不是严格矩形 CSV）；机器消费请以 JSON 为准，Excel/部分解析器会把注释当额外行。

### 8.3 真实验收（120 Case）

| 项 | CSV | JSON |
|---|---|---|
| 行数 / Case 数 | 120 行（17 列） | 120 cases / 3 metrics |
| verdict 计数 | 31 / 32 / 57 / 0 / 0 | 31 / 32 / 57 / 0 / 0 |
| item_key / question 完整 | 120/120 | 120/120 |
| same_config / noise | `# same_config=true`、`# noise_notice=` | `true`、`judge_beta=true` |
| 解析 | Python `csv` 读取 120 行，中文正常 | `JSON.parse` 通过，schema `m3.compare.export.v1` |
| BOM | `EF BB BF`（Excel 中文兼容） | n/a |
| 文件名 | `rag-compare_5328123c_7b2fa311_20261125T074055Z.csv` | 同名 `.json` |

- 页面渲染 120 行，缺失标签 0；导出按钮截图：`docs/04-development/assets/m3-p13/compare-export-buttons.png`。
- **权限**：纯前端 Blob 下载，不上传服务端/对象存储；只包含当前登录用户已加载的 Run 数据。
- **客户数据**：`question` 可能含客户对话内容；导出只在当前用户会话内下载，不生成公开链接（P1-3b 报告与 M4-A 数据权利同样保留此约束）。
- 200 上限与 `same_config=false` 由 mocked 单测覆盖（250 Case → 200 行 + 截断说明）。

### 8.4 测试

| 项 | 结果 |
|---|---|
| 导出模块单测 | 10 passed：CSV 逗号/引号/换行/中文、Excel 注入、CSV/JSON 120 行、250→200、same_config true/false、文件名 |
| Compare UI | 导出按钮加载后可用 |
| API 分页 | 120 条 dataset items 两页拉完 |
| 全量 | 84 files / 435 tests；lint / build 通过 |

## 9. P1-3b：报告“Run 对比”章节（2026-11-25）

> 复用现有报告中心的模板/任务/存储/下载链路；**不新建报告引擎、不做 migration**。
> 对比章节为确定性渲染，不调用报告 Agent，确保数字与对比页一致。

### 9.1 改动

| 层 | 改动 |
|---|---|
| 对比页 | 新增“生成报告”按钮 + 弹窗：标题、格式（Markdown/Excel/PDF），生成到当前数据源下。 |
| 前端快照 | `buildComparisonReportPayload`：在导出快照上补 Top 变好/变差（最多 5 条，按驱动指标绝对变化）、对比页链接、same_config、样本计数。 |
| 报告配置 | `ReportConfig.run_comparison`（存 JSONB config，无 migration）。 |
| 报告服务 | 创建时校验 base/target Run 属于当前用户（跨租户 404）；命中对比配置时跳过 Agent，追加“Run 对比”section，再走原 markdown/excel/pdf 渲染与存储。 |
| 模板 | 对比报告的质量/知识/洞察概览显示“本报告为 Run 对比报告，不含…”，避免误导。 |

### 9.2 章节内容

- **Base / Target**：Run ID、dataset/version、mode/adapter/top_k、judge model/prompt、完成时间。
- **指标**：F/C/R 的 base / target / delta；样本状态 invalid / failed / skipped / unprocessed。
- **Case 汇总**：变好 / 变差 / 不变 / invalid / 未处理，对齐/导出数，200 截断说明。
- **Top 变化**：最多 5 条变好、5 条变差，带 item_key/问题、驱动指标、delta、说明。
- **Beta 提示**：Judge beta；same_config=true 时追加“同配置比较”噪声警告；delta 不代表因果。
- **链接**：对比页链接 + “导出 CSV / 导出 JSON”提示。

### 9.3 真实验收（120 Case）

| 项 | 结果 |
|---|---|
| 报告 | `a4290722-9550-4ac5-a047-fe74c0d7abbc`，completed，comprehensive / markdown |
| 章节 | ✅ “Run 对比”存在 |
| 指标 | ✅ F 0.776→0.801（+0.026）、C 0.128→0.125（-0.003）、R 0.498→0.488（-0.010） |
| Case 汇总 | ✅ 变好 31 / 变差 32 / 不变 57 / invalid 0 / 未处理 0（合计 120） |
| Top 变好 | ✅ `P12-002/017/027/037/047`，与导出 JSON 排序完全一致 |
| Top 变差 | ✅ `P12-007/072/015/030/055`，与导出 JSON 排序完全一致 |
| same_config | ✅ 报告显示“同配置比较”噪声警告 |
| noise | ✅ “Judge beta 噪声提示”存在 |
| 导出链接 | ✅ 对比页链接 + CSV/JSON 导出提示 |
| 打开 | ✅ 报告中心预览可打开，数字与对比页一致 |
| 跨租户 | ✅ 引用他人 Run 创建报告返回 404 `RAG_EVALUATION_NOT_FOUND`（集成测试） |

截图：

- `docs/04-development/assets/m3-p13/compare-report-preview.png`（摘要/章节开头）
- `docs/04-development/assets/m3-p13/compare-report-cases.png`（指标、样本状态、Case 汇总、Top 变好/变差）

### 9.4 测试

| 项 | 结果 |
|---|---|
| 报告章节单测 | 6 passed：数字/噪声/same_config false/空 Top/200 截断/Markdown+Excel 模板渲染 |
| 报告集成 | 2 passed：对比报告不调用 Agent + 跨租户 404；报告套件 15 passed |
| 前端 | 84 files / 439 tests；导出/报告快照、Top 5 排序、Compare UI |
| lint / build / mypy / import-linter | 通过 |

### 9.5 备注

- CSV 顶部 `#` 元数据块不是严格 CSV；机器消费以 JSON 为准（P1-3a 备注）。
- `question` 可能含客户数据；导出与报告均只允许当前用户/租户，不生成公开链接；M4-A 数据权利继续保留此约束。
