# 上线验收执行记录（2026-10-27）

本目录存放「15-上线验收清单」中**可在本机真实执行**的验收产物与脚本。目标：把"代码写完"推进到"可上线证据"。

## 1. 本轮执行结果

| 验收项 | 结果 | 证据 |
| --- | --- | --- |
| 真实后端联调 | ✅ **121/121 步骤通过**，覆盖 **44 个唯一接口**（method+path） | [`smoke-report.md`](./smoke-report.md)、[`smoke-run.log`](./smoke-run.log) |
| 错误码 | ✅ 401/403/404/409/413/415/422 实测；429 单独实测（第 59 次触发，含 `Retry-After`/`X-RateLimit-*`）；500/503 需故障注入，未在健康栈实测 | [`smoke-report.md`](./smoke-report.md)、[`rate-limit.txt`](./rate-limit.txt) |
| 浏览器走查（5 档） | ✅ 375/768/1024/1280/1920；**横向溢出 0 处**；30 张截图 | [`browser-audit.md`](./browser-audit.md)、[`browser-audit.json`](./browser-audit.json)、`screenshots/`（未入库） |
| Modal/Drawer 越界 | ✅ 0 问题；新建数据源 Drawer、生成报告 Modal 均在视口内，Esc 可关闭 | [`browser-audit.json`](./browser-audit.json) |
| 键盘走查 | ⚠️ 自动化 Tab 序列已采集（登录页）；焦点陷阱/完整人工走查未做 | [`browser-audit.md`](./browser-audit.md) |
| 可访问性（WCAG A/AA） | ✅ axe 违规 **47 → 0**（修复对比度/按钮名/进度名/滚动区可聚焦）；Lighthouse 登录页 **a11y 100** | [`browser-audit.md`](./browser-audit.md)、[`lighthouse-login.json`](./lighthouse-login.json) |
| Sentry 上报链路 | ✅ 本地接收端收到 envelope，含异常类型与消息（SaaS DSN 由部署方填） | 脚本 `backend/scripts/sentry_capture_check.py` |
| 生产 .env 模板 | ✅ 结构校验通过（生产不变量：Secure Cookie/DEBUG=False/eager=False 等） | `backend/.env.production.example`、`backend/scripts/prod_env_check.py` |
| compose 配置 | ✅ `docker compose config -q` 通过 | 命令记录 |
| /metrics 数据源 | ✅ 端点 200 可抓取；⚠️ 发现 LLM/Agent 指标在 Celery worker 进程，当前 Prometheus 只抓 api:8000（见 §4） | 手工 curl |

## 2. 阻塞项（需部署机/环境）

| 项 | 原因 | 解除条件 |
| --- | --- | --- |
| 镜像构建 + prod compose 起 api/celery/nginx | 本机 Docker Desktop engine 不可用（`npipe` 连接失败，尝试启动 120s 未就绪） | 在部署机（或启动 Docker daemon 后）执行 `docker compose -f docker-compose.prod.yml up -d --build` |
| Prometheus/Grafana 实跑 | 依赖上一条 Docker | 同上，加 `--profile monitoring` |
| 部署环境 `/dashboard` 刷新/登录 | 依赖 nginx + 容器 | 同上 |

## 3. 本轮发现并修复的缺陷

| # | 缺陷 | 修复 |
| --- | --- | --- |
| 1 | 数据源 `force=true` 物理删除时，若存在 `llm_calls` 记录 → **500**（外键 NO ACTION） | 迁移 `008`：`llm_calls.datasource_id` 改为 `ON DELETE SET NULL`（成本记录保留）；新增回归测试 |
| 2 | 清洗结果列表不含 `id`，前端/联调无法调用详情端点（历史已知限制） | `CleanedDataItem` 增加 `id`；联调详情端点由 404 变 200 |
| 3 | axe 报 47 条 serious/critical（对比度、按钮名、progressbar 名、滚动区不可聚焦） | 主色 `primary-500→600`、Select 增加 `ariaLabel`、Progress 增加 `aria-label`、Table 滚动区 `tabIndex`；axe 复跑 0 |
| 4 | 登录页脚注 `text-gray-400` 对比度 2.53 | 改为 `text-gray-500`；Lighthouse a11y 95→100 |

## 4. 未解决的验收发现（需排期）

1. ~~Prometheus 抓不到 Agent/LLM 指标~~ **已修复（2026-10-27）**：
   - worker 启动 `prometheus_client.start_http_server(9109)`（`worker_process_init` + 显式导入 metrics 注册指标）；
   - Prometheus 增加 `aiinsight-worker` job（target `worker:9109`）；
   - 实测：`llm_calls_total{agent_name="cleaning_agent",model="deepseek-flash",status="success"} = 1`，Grafana 看板 2 个 provisioning 成功。
2. **500/503 错误码未真实触发**：需要故障注入（DB 断开/降级 STOPPED），当前由单测/异常处理器覆盖。
3. **WebAIM 人工对比度抽查**：已用 axe（0 违规）+ Lighthouse（100）替代自动化部分，人工视觉走查仍建议部署前补。
4. **键盘焦点陷阱**：仅采集了 Tab 序列，Modal/Drawer 的 focus trap 未自动化验证。

## 5. 如何复跑

前置：后端 8000（建议 `RATE_LIMIT_ENABLED=false`、`HF_HUB_OFFLINE=1`）、Celery worker（`-P solo`）、前端 5173。

```powershell
# 真实联调（会真实调用 LLM，产生少量费用）
cd backend
.\venv\Scripts\python.exe scripts\acceptance_smoke.py --report ..\ops\acceptance\smoke-report.md

# 429 限流（需另起一个 limiter 开启的实例，如 8001）
#   uvicorn ... --port 8001
#   python 脚本见历史记录（70 次 /users/me，第 59 次 429）

# Sentry 上报链路
.\venv\Scripts\python.exe scripts\sentry_capture_check.py

# 生产 env 模板校验
.\venv\Scripts\python.exe scripts\prod_env_check.py

# 浏览器走查（5 视口 + axe + Modal/Drawer + 键盘）
cd frontend
node e2e/acceptance/browser_audit.mjs

# Lighthouse（使用系统 Edge）
$env:CHROME_PATH="C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
npx lighthouse@12 http://127.0.0.1:5173/login --only-categories=accessibility --output=json --output-path=..\ops\acceptance\lighthouse-login.json
```

## 6. 结论

- **代码层 MVP 功能完整**；本轮把「真实联调、错误码、响应式、Modal、a11y、Sentry 链路、生产配置模板」推进到可复核证据；
- **上线仍差 3 项环境动作**：镜像/容器实跑、监控栈实跑、部署域名验证；均由本机 Docker daemon 不可用阻塞；
- **另需排期修复**：worker metrics 抓取（影响可观测实际效果）。
