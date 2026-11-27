# P0-B 端到端演示 runbook（UI-only）

> 状态：`ready_for_non_developer_test`
> 环境：独立 demo 库 `aiinsight_demo`（**不写 aiinsight_preprod，不碰生产**）
> 目标：非开发人员不碰命令行，≤30 分钟完成一次完整流程
> 当前 demo 栈：API `http://127.0.0.1:8000`，前端 `http://127.0.0.1:5173`

## 1. 环境隔离

| 项 | 值 |
|---|---|
| DB | VM PostgreSQL，database `aiinsight_demo`（从空库迁移到 025） |
| Redis | DB 6 app / 7 broker / 8 result |
| Storage | `backend/.storage/demo-p0b`，local |
| RAG | `RAG_ADAPTER=mock` |
| flag | `TENANT_ENFORCEMENT_ENABLED=false` |
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

## 3. 测试者操作（UI only，目标 ≤30 分钟）

| # | 操作 | 预期 | 预算 |
|---|---|---|---|
| 1 | 打开 `http://127.0.0.1:5173/login`，登录 demo 账号 | 进入 Dashboard | 2 min |
| 2 | 数据源管理 → 新建数据源（名称 `P0B 演示数据源`） | 创建成功 | 2 min |
| 3 | 上传 `docs/releases/p0b-demo-sample.txt` | 202；清洗任务完成 | 5 min |
| 4 | 质量评估 → 新建评估 → 运行 | 结果列表出现，分数/问题可见 | 5 min |
| 5 | 知识库 → 选择数据源 → 提取知识（或手动新建 1 条 FAQ） | 至少 1 条知识 | 3 min |
| 6 | QA 数据集 → 新建数据集（名称 `P0B 演示评测集`） | 数据集创建并选中 | 2 min |
| 7 | 新建草稿版本 → 导入 `p0b-demo-dataset.json` → 发布 | 5 条导入、发布成功、显示“已发布 · 不可变” | 5 min |
| 8 | 在已发布版本点「发起评测」 | 跳到 RAG 评测，弹窗已预选数据集/版本 | 1 min |
| 9 | 第一次 Run：adapter=mock，top_k=3，limit=5，创建 | Run 完成，详情可见 | 2 min |
| 10 | 第二次 Run：同一版本，top_k=5，limit=5 | 第二个 Run 完成 | 2 min |
| 11 | 对比 Run：选两个 Run，查看同配置提示/指标/导出 | 对比页显示不同 top_k（非 same-config 噪声） | 2 min |
| 12 | 报告中心 → 生成 markdown 报告 → 下载 | 报告 completed，可下载 | 3 min |

> 预算合计约 34 min；熟练操作应在 30 min 内。若某一步 LLM 超时，记录卡点，不把手动重试算作通过。

## 4. 验收检查

- [ ] 全程未使用命令行、SQL、seed 脚本；
- [ ] 空状态 CTA 能串起来（无数据源 → 数据源页；无数据集 → QA 数据集页）；
- [ ] QA 数据集发布后可直接「发起评测」，弹窗预选版本；
- [ ] 两个 Run 的 `top_k` 分别为 3 / 5，对比页不提示 same-config；
- [ ] Beta 提示可见（RAG 评测页 / Judge beta）；
- [ ] 报告完成且可下载；
- [ ] 未访问/写入 `aiinsight_preprod`、未使用生产 bucket；
- [ ] 记录耗时、卡点、截图。

## 5. 需要回传的证据

| 项 | 内容 |
|---|---|
| 测试者 | 姓名/角色（必须非开发） |
| 时间 | 开始/结束/总耗时 |
| 浏览器 | 名称/版本 |
| 数据源 / Task ID | |
| 数据集 / 版本 ID | |
| Run1 / Run2 ID | |
| 对比结果 | 两个 top_k、指标/提示 |
| Report ID | |
| 截图 | 登录、数据源、清洗、质量、知识库、数据集导入、发布、评测弹窗、Run 详情、对比、报告下载、Beta 提示 |
| 卡点 | 步骤/现象/是否重试/耗时 |
| CLI | 必须为“未使用” |
| 隔离确认 | 未写 preprod / 未碰生产 |

## 6. 已知限制与话术

- RAG Judge 为 **beta**；invalid / skipped / 噪声按页面原样解释，不承诺 target 通过率。
- 本次使用 `mock` 适配器，验证的是产品链路，不是真实知识库质量。
- 不把“链路跑通”写成“质量已验收”。
- 演示数据仅测试用，不导入真实客户数据。

## 7. 结束后

- 测试者回传 `p0b-e2e-test-record.md` + 截图；
- 开发停止 demo API/worker/Vite（或按约定保留）；
- P0-B 验收通过后再开 P0-C；P0-C 前不扩 scope。
