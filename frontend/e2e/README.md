# E2E 测试（Playwright，T1）

对**真实前端 + 真实后端 + 真实 PostgreSQL/Redis** 运行浏览器用例，不 mock API。
覆盖：认证/守卫、导航、数据源、知识库（手动 CRUD）、报告表单（含 PDF 选项）、404。

## 前置

```bash
# 1) 后端（backend 目录；需要 backend/.env 指向可用的 PG/Redis）
cd backend
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 2) 前端（frontend 目录；/api 会代理到 8000）
cd frontend
npm run dev
```

浏览器：本机默认用系统已安装的 **Edge**（`channel=msedge`，免下载）；
其他环境先 `npx playwright install chromium`，并设置 `E2E_BROWSER_CHANNEL=chromium`。

## 运行

```bash
cd frontend
npm run test:e2e          # 无头
npm run test:e2e:headed   # 有头（观察交互）
npm run test:e2e:ui       # Playwright UI 模式
```

可选环境变量：

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `E2E_BASE_URL` | `http://localhost:5173` | 前端地址 |
| `E2E_API_ORIGIN` | `http://localhost:8000` | 后端 origin（不含 `/api/v1`） |
| `E2E_API_PREFIX` | `/api/v1` | API 前缀 |
| `E2E_BROWSER_CHANNEL` | `msedge` | `msedge` / `chrome` / `chromium` |

## 环境注意事项

- **限流**：整套用例会多次登录，建议后端以 `RATE_LIMIT_ENABLED=false` 启动，避免 60/min 限流导致偶发 429。
- **嵌入模型**：知识库“新建条目”会同步计算 embedding。若机器无法访问 huggingface.co，
  请给后端设置 `HF_HUB_OFFLINE=1`、`TRANSFORMERS_OFFLINE=1`（此时 embedding 置空但条目可创建）。
- **测试数据**：每个 run 通过 API 注册唯一用户（`e2e-<ts>@example.com`），
  用例创建的数据源/FAQ 在结束时清理；用户账号无删除接口，会保留在开发库。
- **LLM**：用例刻意不触发清洗/评估/报告生成，避免真实计费与不确定耗时。

## 产物

失败时生成 `test-results/`（截图、trace）与 `playwright-report/`（HTML 报告），均已在 `.gitignore` 中忽略。
调试：`npx playwright show-trace test-results/<case>/trace.zip`。
