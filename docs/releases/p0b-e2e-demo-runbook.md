# P0-B 端到端演示 runbook（人类 UI 测试）

> 状态：`pending_non_developer_test`
> AI 功能证据：`docs/releases/p0b-e2e-test-record.md`（AI 执行，仅功能证据，**不作验收**）
> 环境：独立 demo 库 `aiinsight_demo`（**不写 aiinsight_preprod，不碰生产**）
> 目标：未参与开发的人类测试者，从空库完成一次完整流程，≤30 分钟
> 当前 demo 栈：API `http://127.0.0.1:8000`，前端 `http://127.0.0.1:5173`

## 0. 测试者资格

| 项 | 要求 |
|---|---|
| 必须 | **人类**，全程自己操作浏览器 |
| 优先 | QA / 产品 / 业务同学，未参与 P0-B 开发 |
| 备选 | 找不到人时由 owner 本人测试，记录标 `owner acceptance`，不冒充独立测试 |
| 不能是 | 提交 P0-B 代码的开发、AI agent、或全程被开发逐步指导的人 |
| 开发角色 | 只负责环境和故障响应，不逐步指导操作、不代点页面 |

## 1. 环境隔离

| 项 | 值 |
|---|---|
| DB | VM PostgreSQL，database `aiinsight_demo`；**从空库迁移到 025，测试前重置为空** |
| Redis | DB 6 app / 7 broker / 8 result |
| Storage | `backend/.storage/demo-p0b`，local（测试前清空） |
| RAG | `RAG_ADAPTER=mock` |
| flag | `TENANT_ENFORCEMENT_ENABLED=false` |
| 限流 | **保持默认开启**（`RATE_LIMIT_ENABLED=true`），不得为通过测试而关闭 |
| 账号 | `demo-p0b@example.com`（tenant_admin）；密码只在本地安全文件 `C:\Users\The Fool\AppData\Local\Temp\opencode\p0b_demo_credentials.json` |
| 禁止 | 不使用 preprod 证据库；不使用生产 bucket/数据 |

> 演示数据只用 `docs/releases/p0b-demo-sample.txt` 和 `p0b-demo-dataset.json`，不含真实客户数据。

## 2. 启动（开发/运维，测试者无需执行）

```powershell
cd backend
$env:DATABASE_URL="postgresql://<user>:<password>@192.168.150.100:5433/aiinsight_demo"
$env:REDIS_URL="redis://192.168.150.100:6379/6"
$env:CELERY_BROKER_URL="redis://192.168.150.100:6379/7"
$env:CELERY_RESULT_BACKEND="redis://192.168.150.100:6379/8"
$env:STORAGE_BACKEND="local"
$env:STORAGE_LOCAL_DIR=".storage/demo-p0b"
$env:RAG_ADAPTER="mock"
$env:TENANT_ENFORCEMENT_ENABLED="false"
$env:RATE_LIMIT_ENABLED="true"
$env:ALLOW_SERVER_KEY_FALLBACK="true"
$env:DEEPSEEK_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
$env:DEEPSEEK_API_KEY=$env:DASHSCOPE_API_KEY
$env:DEFAULT_LLM_MODEL="qwen-flash"
.\venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
.\venv\Scripts\celery.exe -A app.core.celery.celery_app worker -l info -P solo -Q default,clean
cd ..\frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

> worker 必须带 `-Q default,clean`，否则上传后的清洗任务会一直 pending。
> 限流必须保持开启；若页面出现 429，记录为卡点，不要关闭限流绕过。

## 3. 测试者操作（UI only，目标 ≤30 分钟）

| # | 操作 | 预期 | 预算 |
|---|---|---|---|
| 1 | 打开 `http://127.0.0.1:5173/login`，登录 demo 账号 | 进入 Dashboard | 1 min |
| 2 | 空状态 CTA 巡检（见 3.1） | 每个 CTA 可点击并到正确页面 | 3 min |
| 3 | 数据源管理 → 新建数据源（名称 `P0B 演示数据源`） | 创建成功 | 2 min |
| 4 | 上传 `docs/releases/p0b-demo-sample.txt` | 202；清洗任务完成 | 4 min |
| 5 | 质量评估 → 新建评估 → 运行 | 结果列表出现，分数/问题可见 | 3 min |
| 6 | 知识库 → 选择数据源 → 提取知识（异步） | 至少 1 条知识 | 2 min |
| 7 | QA 数据集 → 新建数据集（名称 `P0B 演示评测集`） | 数据集创建并选中 | 1 min |
| 8 | 新建草稿版本 → 导入 `p0b-demo-dataset.json` → 发布 | 5 条导入、发布成功、显示“已发布 · 不可变” | 3 min |
| 9 | 在已发布版本点「发起评测」 | 弹窗已预选数据集/版本 | 1 min |
| 10 | 第一次 Run：adapter=mock，top_k=3，limit=5，创建 | Run 完成，详情可见 | 2 min |
| 11 | 第二次 Run：同一版本，top_k=5，limit=5 | 第二个 Run 完成 | 2 min |
| 12 | 对比 Run：选两个 Run，查看指标/提示并导出 CSV | 对比页显示不同 top_k（非 same-config 噪声） | 2 min |
| 13 | 报告中心 → 生成 markdown 报告 → 下载 | 报告 completed，可下载 | 2 min |
| 14 | 查看 RAG 评测页 / Run 详情的 Beta 提示 | Beta 文案可见 | 1 min |

> 预算合计约 29 min；超过 30 min 必须记录卡点和实际耗时，不把重试直接算作通过。

### 3.1 空状态 CTA 清单（必须逐项点击）

| 页面 | 空状态预期 | 点击后应到达 | 截图 |
|---|---|---|---|
| 数据源管理 | “暂无数据源，先创建一个吧” +「新建数据源」 | 打开新建数据源 Drawer | 必存 |
| 数据清洗 | “尚未选择数据源” +「去数据源管理」 | `/data-sources` | 必存 |
| 质量评估 | “尚未选择数据源” +「去数据源管理」 | `/data-sources` | 必存 |
| 知识库 | “尚未选择数据源” +「去数据源管理」 | `/data-sources` | 必存 |
| 报告中心 | “尚未选择数据源” +「去数据源管理」 | `/data-sources` | 必存 |
| QA 数据集 | “还没有 QA 数据集” +「新建数据集」 | 打开新建数据集弹窗 | 必存 |
| RAG 评测 | “还没有 RAG 评测 Run” +「新建评测」 | 打开新建评测弹窗；无已发布版本时可点「QA 数据集」链接 | 必存 |

> 空状态巡检只验证“入口能串起来”，不创建业务数据；巡检后再从数据源开始主流程。

## 4. 验收检查

- [ ] 测试者是未参与开发的人类（或 owner，记录标 owner acceptance）；
- [ ] 全程浏览器操作，未使用 CLI/SQL/seed；
- [ ] 空状态 CTA 7 项全部勾选并截图；
- [ ] 数据源→上传→清洗→质量→知识库→数据集→发布→评测→两个 Run→对比/CSV→报告/下载→Beta 全流程完成；
- [ ] 两个 Run 的 `top_k` 分别为 3 / 5，对比页不提示 same-config；
- [ ] 默认限流下无阻塞；若出现 429，已记录页面/步骤/是否重试；
- [ ] 未访问/写入 `aiinsight_preprod`、未使用生产 bucket；
- [ ] 真实人类耗时 ≤30 分钟；超过已说明卡点；
- [ ] 记录完整（姓名/角色、时间、ID、截图、卡点）。

## 5. 需要回传的证据

| 项 | 内容 |
|---|---|
| 测试者 | 姓名/角色/团队；是否参与 P0-B 开发；是否 owner |
| 时间 | 开始/结束/总耗时（真实人类时间） |
| 浏览器 | 名称/版本 |
| 空状态 CTA | 7 个页面各一张截图 + 点击后落点 |
| 数据源 / Task ID | |
| 数据集 / 版本 ID | |
| Run1 / Run2 ID | 两个不同 top_k |
| 对比结果 | 两个 top_k、指标/提示、CSV 文件 |
| Report ID | 报告状态与下载文件 |
| 限流 | 是否出现 429、出现页面、是否重试 |
| CLI | 必须为“未使用” |
| 隔离确认 | 未写 preprod / 未碰生产 |

## 6. 已知限制与话术

- RAG Judge 为 **beta**；invalid / skipped / 噪声按页面原样解释，不承诺 target 通过率。
- 本次使用 `mock` 适配器，验证的是产品链路，不是真实知识库质量。
- 不把“链路跑通”写成“质量已验收”。
- 演示数据仅测试用，不导入真实客户数据。
- 手工新建 FAQ 首次会同步加载 embedding，可能超过前端 30s；P1 已知问题，演示走“提取知识（异步）”。
- 默认限流下若出现 429，属于待评估的体验问题（P1），记录即可，不关闭限流绕过。

## 7. 结束后

- 测试者回传 `p0b-e2e-test-record.md` + 截图；
- owner 根据人类测试结果给 P0-B accepted / blocked；
- P0-B 通过后再开 P0-C；P0-C 前不扩 scope；
- 开发停止 demo API/worker/Vite（或按约定保留）。
