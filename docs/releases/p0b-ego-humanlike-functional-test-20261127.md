# P0-B 类人操作功能测试记录（ego-browser）

> 状态：`AI_HUMANLIKE_TEST / FIXED_SELF_CHECK_PASSED / PENDING_HUMAN_RETEST`
> 测试者：**AI agent（owner 授权，ego lite 本地浏览器操作）**；不是人类，不冒充独立测试。
> 原始结论：核心链路可跑通，但空状态 CTA 有断点、质量/知识列表不自动刷新；P0-B blocked。
> 2026-11-27 修复后：F1/F2/F3 + stale localStorage 已修，AI 自检通过；仍待人类复测，不标 accepted。
> 证据目录：`docs/releases/evidence/p0b-ego-20261127/`

## 1. 测试范围

| 项 | 内容 |
|---|---|
| 证据窗口 | 2026-11-27 21:41:44–22:01:59（UTC+8），墙钟 20m15s；含两次本地服务重启 |
| 浏览器 | ego lite 0.6.3.17，本地 Chromium |
| 环境 | `aiinsight_demo` 空库；`RAG_ADAPTER=mock`；`TENANT_ENFORCEMENT_ENABLED=false` |
| 限流 | **`RATE_LIMIT_ENABLED=true` 默认开启**；本轮未出现 429 |
| 测试方式 | 业务操作全部在浏览器完成；环境重置/seed 在测试前由开发/运维完成；ID 用只读 DB/API 核对 |
| 隔离 | 未写 `aiinsight_preprod`，未碰生产 |

> 这是 11/27 的提前类人功能测试，不占用 11/30 10:00–10:45 的正式人类窗口。因测试者仍是 AI，**不能作为 P0-B accepted**。

## 2. 空状态 CTA 结果

| # | 页面 | 实际空状态 / CTA | 点击结果 | 结论 |
|---|---|---|---|---|
| 1 | 数据清洗 | “暂无清洗任务” +「新建清洗任务」 | 打开“新建清洗任务”弹窗；数据源下拉为“请选择数据源”，**没有可选数据源，也没有去数据源管理入口** | **FAIL / 阻塞** |
| 2 | 质量评估 | “尚未选择数据源” +「去数据源管理」 | 到 `/data-sources` | PASS |
| 3 | 知识库 | “尚未选择数据源” +「去数据源管理」 | 到 `/data-sources` | PASS |
| 4 | 报告中心 | “尚未选择数据源” +「去数据源管理」 | 到 `/data-sources` | PASS |
| 5 | QA 数据集 | “还没有 QA 数据集” +「新建数据集」 | 打开新建数据集弹窗 | PASS |
| 6 | RAG 评测 | “还没有 RAG 评测 Run” +「新建评测」 | 打开新建评测弹窗；无已发布版本时可点「QA 数据集」链接并到达 `/qa-datasets` | PASS |
| 7 | 对比入口 | “至少需要两个 completed Run” +「返回 Run 列表」 | 从 RAG 列表「对比 Run」进入；空态提示正确 | PASS |

补充：数据源管理空态「新建数据源」可打开 Drawer（PASS，但该页不在用户列的 7 项内）。

> 第 1 项是本轮最明确的 P0-B 验收失败：从空库进入数据清洗，用户被带到一个没有数据源可选的弹窗，无法继续。

## 3. 主流程结果

| 步骤 | 结果 | 证据 |
|---|---|---|
| 数据源创建 + 上传 | `P0B 类人测试数据源 20261127`，上传 `p0b-demo-sample.txt` | 数据源 `5595b7ab-1231-43ba-a198-cd1b8dd209aa` |
| 清洗 | completed，5 条结果 | Task `20db1ac3-c683-49da-b344-dc928b22f844` |
| 质量评估 | completed，5 条，平均 72.1；**需手动“刷新”才显示** | Task `aadaf804-7861-4711-94da-32fbac6bd3a0` |
| 知识提取 | completed，5 条 FAQ；**需整页刷新才显示** | Task `0a3a5b96-ce48-4822-80fe-c30704ed2624` |
| QA 数据集 | 创建、v1 草稿、导入 5 条、发布“已发布 · 不可变” | Dataset `28ed3ce8-1f1b-4d5a-9bb9-58138a16f6cb`；Version `0e7234e6-a600-44bc-99f4-f94d9dbbf875` |
| Run1 | completed，5/5，`top_k=3`；F 0.60 / C 0.32 / R 0.48 | `ea63f595-e6ab-46fa-a362-32cce6b0bf32` |
| Run2 | completed，5/5，`top_k=5`；F 0.60 / C 0.30 / R 0.50 | `ab7a19d2-cf56-4f3c-a7d0-d833e97b9b98` |
| 对比 + CSV | Base/Target 均为同一版本；未出现“同配置比较”强警告；CSV 下载成功 | `compare-ego.csv` |
| 报告 + 下载 | Markdown 2.4 KB，completed；下载成功 | Report `c0b368c1-a278-4275-bac3-6045427deb9d` |
| Beta 提示 | RAG 列表、Run 详情、对比页均可见 | 截图 `13`、`37`、`40a` |

## 4. 发现

| # | 严重级别 | 现象 | 证据 |
|---|---|---|---|
| F1 | **P0-B 阻塞** | 数据清洗空态 CTA 是“新建清洗任务”，打开弹窗后没有数据源可选，也没有“去数据源管理”入口；空库用户无法从该页继续 | `03-empty-data-cleaning.png`、`04-data-cleaning-new-task.png` |
| F2 | P1 | 质量评估任务已完成（21:48:06），页面 21:50:05 仍显示 0 条；点“刷新”后 21:50:30 才出现 5 条 | `20a-quality-current.png`、`20-quality-results.png`；Task `aadaf804...` |
| F3 | P1 | 知识提取任务已完成（21:51:57，5 条 FAQ），页面 21:53:57 仍显示“暂无知识条目”；整页刷新后才出现 5 条 | `23a-knowledge-current.png`、`23-knowledge-extracted.png`；Task `0a3a5b96...` |
| F4 | 环境/测试保障 | 本地 API + Vite 在 20 分钟窗口内两次退出，重启后数据保留；疑似后台进程监管问题，不是业务代码错误 | API/前端各重启一次；无 429 |
| F5 | 测试工具 | ego lite 的 TaskSpace 两次丢失，重建后继续；不是产品缺陷 | TaskSpace 1 → 重建 |
| F6 | 测试伪影 | 空库重置后浏览器 localStorage 仍保留旧 `aiih.datasource`，质量页首次显示“数据源不存在”；清除后正常。全新人类浏览器不会带此状态 | 不作为产品缺陷计入 |

## 5. 结论与建议

1. **原始结论：P0-B 建议 blocked**（已按第 6 节修复）：F1 直接违反“空状态 CTA 全部勾选”的验收条件；F2/F3 让非开发用户误以为任务失败。
2. 修复建议：
   - 数据清洗空态在无数据源时提供“去数据源管理/新建数据源”入口，或禁用“新建清洗任务”并给出明确指引；
   - 质量任务完成后失效/重取质量结果查询；
   - 知识提取完成后失效/重取 FAQ 列表；
   - 本地 demo 启动方式改为稳定终端/进程守护，确保 30 分钟测试窗口不中断。
3. 修复后由**人类**按 `p0b-e2e-demo-runbook.md` 复测；AI 本次结果只作功能证据，不作验收通过。
4. P0-C 继续不开始。

## 6. 修复自检（2026-11-27）

| 项 | 修复 | 自检 |
|---|---|---|
| F1 数据清洗空态 | 无数据源时展示「新建数据源 / 去数据源管理」，禁用“新建清洗任务”；弹窗无数据源时给 CTA，有数据源时默认选中 | 浏览器：有数据源时弹窗显示真实选项 PASS；无数据源 CTA 单测 PASS |
| F2 质量结果 | 订阅任务流，`evaluate` 任务 completed 后失效 quality 查询 | 浏览器：新评估完成后质量总数 5 → 10，未点“刷新” PASS |
| F3 FAQ 列表 | 订阅任务流，`extract` 任务 completed 后失效 knowledge 查询 | 浏览器：提取 202 后自动发起 FAQ GET PASS |
| stale localStorage | 列表为空时清 currentId；页面查询 404 时清 currentId 并回到数据源引导 | 浏览器：伪造 currentId 后不再出现“数据源不存在” PASS |
| 稳定进程 | 新增 `scripts/demo-p0b.ps1`，独立终端启动 API/worker/Vite，健康检查后保持窗口 | 语法检查 PASS；人类测试前需按 runbook 预热 10 分钟 |

验证命令：

- `npm run test:run`：**460 passed**
- `npm run lint`：通过
- `npm run build`：通过
- 自检原始结果：`docs/releases/evidence/p0b-ego-20261127/fix-selfcheck-20261127.json`

> 以上是 AI 修复自检，不是人类验收；P0-B 仍保持 blocked，直到人类按 runbook 复测通过。自检产生的新质量/知识任务数据会在人类测试前通过重置 demo 库清掉。

## 7. 证据索引

| 文件 | 内容 |
|---|---|
| `03-empty-data-cleaning.png` | 数据清洗空态 |
| `04-data-cleaning-new-task.png` | 空态 CTA 打开弹窗，无数据源可选 |
| `05/06-empty-quality` | 质量空态 + CTA 到数据源 |
| `07/08-empty-knowledge` | 知识库空态 + CTA 到数据源 |
| `09/10-empty-reports` | 报告空态 + CTA 到数据源 |
| `11/12-empty-qa` | QA 数据集空态 + 新建弹窗 |
| `13/14-empty-rag` | RAG 空态 + 新建弹窗（含 QA 数据集链接） |
| `15-empty-compare.png` | 对比入口空态 |
| `20a-quality-current.png` | 质量任务完成后仍 0 条 |
| `20-quality-results.png` | 手动刷新后 5 条 |
| `23a-knowledge-current.png` | 知识提取完成后仍空 |
| `23-knowledge-extracted.png` | 整页刷新后 5 条 FAQ |
| `27-version-created.png` | 草稿 v1 |
| `29-imported-5.png` | 导入 5 条 |
| `31-published.png` | 已发布 · 不可变 |
| `32-eval-modal-preselected.png` | 发起评测，版本已预选 |
| `34-run1-completed-list.png` | Run1 completed |
| `37-both-runs-completed.png` | 两个 Run completed |
| `40a-compare-base-selected.png` | 对比指标 + Beta/噪声提示 |
| `42-report-created-toast.png` | 报告 completed + 下载 |
| `compare-ego.csv` | 对比 CSV |
| `report-ego.md` | 报告正文 |

> 本记录由 AI 类人操作产生，**不是人类验收记录**。P0-B 是否 blocked、是否修复后复测，由 owner 确认。
