# M3 P0：两 Run 对比

> 状态：`implemented` / `verified`（待 accepted）；前端只读，无新后端接口。
> 日期：2026-11-24
> 入口：`/rag-evaluations/compare?base=<runId>&target=<runId>`；Run 列表「对比 Run」、Run 详情「对比此 Run」。

## 1. 范围

| 项 | 内容 |
|---|---|
| 目标 | 同一数据集版本下，比较两个 completed Run 的指标与 Case 变化 |
| Run 选择 | 仅 completed；优先同 dataset + version |
| 指标 | F / C / R 的 base、target、delta；invalid / failed / skipped / unprocessed 分开 |
| Case diff | 按 `dataset_item_id` 对齐；`变好 / 变差 / 不变 / invalid / 未处理` |
| 钻取 | 点击 Case 跳到 M2 的 Case 详情 |
| 导出 | 不做（P1 再接报告） |

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

## 5. 已知问题（P1）

- `partial_failed` Run `9c771d04…`：Windows Celery solo 下第二个任务首个 item 出现 `RuntimeError: Event loop is closed`（asyncpg 连接池跨 `asyncio.run` 复用）；重启 worker 后正常。建议后端做 engine dispose 或持久 loop。
- 对比页复用 M2 的 100 条结果上限；更大 Run 需要分页对齐。
- 无导出；P1 接报告。
- 401 竞态仍在（M2 P1 backlog）。

## 6. 边界

- 不改 target、Prompt、fixture、Judge；不跑 10/40。
- 不做 pairwise 显著性、不做实验配置管理、不做自动优化。
- v1.2.5 保持 beta / inactive；F/C/R 不作 M1 证据。
- M2 P0 已 accepted；M3 P0 待 accepted。
