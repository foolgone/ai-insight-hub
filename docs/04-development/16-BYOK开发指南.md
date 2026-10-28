# BYOK 开发指南（修订版）

> **文档编号**：16  
> **文档版本**：v2.3（实现对齐：迁移 009/010/011、全局 428 已落地）  
> **创建日期**：2026年10月28日  
> **修订日期**：2026年10月28日  
> **文档状态**：已按代码库核验 + 业务收敛拍板；实施与验收以本文为准  
> **修正依据**：[17-BYOK勘误与修订实施计划](./17-BYOK勘误与修订实施计划.md)、[BYOK 业务收敛决策稿](../07-review/BYOK-业务收敛-v1.md)（v1 + 2026-10-28 拍板记录）  
> **关联需求**：[04-需求-用户自带LLM-API-Key（BYOK）](../01-requirements/04-需求-用户自带LLM-API-Key（BYOK）.md)（v0.3，已冻结）  
> **关联架构**：[03-数据库设计](../03-architecture/03-数据库设计.md)、[04-API设计](../03-architecture/04-API设计.md)、[05-页面设计规范](../05-design/03-页面设计规范.md)

---

## 修订说明（v1.0 → v2.0）

v1.0 的**方案骨架**保留（Fernet 加密、单表凭据、4 个 API、`key_source` 成本隔离、fallback、AC 划分）。v2.0 按当前代码库逐行核验后，修正了 v1.0 中**会导致编译失败、运行时报错或架构语义错误**的部分，主要变化：

| # | v1.0 的做法 | v2.0 修订 |
|---|---|---|
| 1 | 在 `BaseAgent.invoke` 内抛 428 | **HTTP 依赖守门（428/400）+ worker 前置兜底**；5 条链路是 Celery 异步任务，HTTP 层才能表达 428 |
| 2 | 自造错误码 + `AIInsightHubException(error_code=...)` | 新增 3 条业务码（先回写 API 设计），用 **3 个异常子类**；禁用 `HTTPException(detail={...})` |
| 3 | 成本过滤改 `degradation_middleware.py` | 改 **`CostTracker.get_daily_cost(only_server_key=True)`** |
| 4 | 手工构造 `LLMCall(...)` 写 `key_source` | 沿 **`BaseAgent → CostTracker.track/record_failure → LlmCall`** 四层透传 |
| 5 | 迁移 010 塞 demo 业务数据 | 迁移只建 demo 账号；业务数据走 **`scripts/seed_demo.py`（可重置）** |
| 6 | 前端 `@/lib/api` + 自建 modal | 走 **`endpoints.js → api/*.js → hooks/*.js → components/Modal`** 既有四层 |
| 7 | 测试用不存在的 fixture（`session`/`client_a`） | 用 `tests/integration/conftest.py` 的 **`db_session` / `client` / `test_user`**；E2E 落 `frontend/e2e/` |
| 8 | key 校验注释与实现矛盾、`base_url` 422 而非 400 | Schema 只做基础约束，**语义校验统一 400** |
| 9 | 未说明新增错误码/模型会打挂存量契约测试、未处理存量集成用例的 428 回归、未提 CI/测试环境开关 | **同步 `test_errors.py` / `test_models_schema.py`；`tests/conftest.py` 加 fallback autouse fixture；CI env 补 BYOK 变量** |
| 10 | 时间写入用 aware datetime、脚本缺 sys.path bootstrap、审计/菜单/无障碍细节缺失 | 统一 `_now_naive()`；脚本显式 bootstrap；`mark_invalid` 按 rowcount 写审计；菜单条件渲染；显示按钮移出 `aria-hidden` slot |
| 11 | 业务收敛（2026-10-28 拍板）：不建注册页、demo 验收不要求跑通 AI、逐页 guard 改全局 428、E2E 延后、demo 种子补 5 页 | 见 §11 v2.2 与 [业务收敛决策稿](../07-review/BYOK-业务收敛-v1.md) |

> 逐条勘误（含行号、代码依据、S1/S2/S3 分级）见 [17 号文档](./17-BYOK勘误与修订实施计划.md)。

---

## 目录

1. [前置阅读与前置条件](#1-前置阅读与前置条件)
2. [架构总览](#2-架构总览)
3. [M1：契约 + 存储层 + 加密服务 + 凭据 API](#3-m1契约--存储层--加密服务--凭据-api)
4. [M2：HTTP 守门 + Agent 注入 + 成本隔离](#4-m2http-守门--agent-注入--成本隔离)
5. [M3：前端 Modal + 引导 + 演示账号](#5-m3前端-modal--引导--演示账号)
6. [M4：演示数据 + 安全测试 + 文档同步](#6-m4演示数据--安全测试--文档同步)
7. [测试策略](#7-测试策略)
8. [配置参考](#8-配置参考)
9. [验收清单（AC-BK-01~15）](#9-验收清单ac-bk-0115)
10. [常见问题](#10-常见问题)
11. [变更记录](#11-变更记录)

---

## 1. 前置阅读与前置条件

### 1.1 必读

| 文档 | 重点 |
|---|---|
| 需求文档 §4（功能需求） | FR-BK-01~22，每个 API 与 Agent 的行为 |
| 需求文档 §6（数据模型） | 表结构、`key_source` 语义 |
| 需求文档 §15（风险） | SSRF、密钥丢失、成本冲突 |
| `backend/app/core/llm.py` | `LLMClient` 构造签名、异常族（`LLMAuthenticationError` / `LLMQuotaError` / `LLMRateLimitError`…） |
| `backend/app/agents/base.py` | `invoke` 的 `try/except` 结构（**决定了 428 不能在这里抛**） |
| `backend/app/core/cost_tracker.py` | `llm_calls` 唯一写入口；`get_daily_cost` 是降级唯一数据源 |
| [01-开发规范](./01-开发规范.md) | 错误码/日志/类型注解/前端 API 调用规范 |

### 1.2 前置条件（开工前逐项确认）

- [ ] 本地 PostgreSQL 与 Redis 可用（`docker compose up -d postgres redis`，或本地 VM 数据库，见 `backend/.env.example` 注释）
- [ ] `CREDENTIAL_ENCRYPTION_KEY` 已生成并写入 `backend/.env`
- [ ] 当前迁移 head 是 **008**（revision `9b2d4f6a8c1e`），本次新增 **009 / 010**
- [ ] 需求文档 v0.3 已提交（当前工作区可能有未提交改动，先清理再开工）
- [ ] 已读 17 号勘误文档（避免重复踩坑）

```bash
# 生成 Fernet 密钥（32 字节 base64）
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# 写入 backend/.env
CREDENTIAL_ENCRYPTION_KEY=<上面的输出>
```

### 1.3 交付物与工作量

| 阶段 | 内容 | 预估 |
|---|---|---|
| M0 | 契约（错误码/API/DB 文档）+ 配置 + 依赖 + 需求文档编号回写 | 0.5 人日 |
| M1 | 加密服务 + 模型 + 迁移 009/010（建表 + `key_source`）+ Schema + 凭据服务 + 4 API（含 verify 端点，前端不调用）+ 测试 | 1.25 人日 |
| M2 | 6 处 HTTP 守门 + Agent 注入 + 成本隔离 + 测试 | 1.25 人日 |
| M3 | 前端 Modal/全局 428 弹窗/菜单入口/登录页演示账号（展示+预填） | 0.6 人日 |
| M4 | demo 账号 + 5 页种子数据 + 安全测试 + 文档同步（E2E 本期延后） | 0.6 人日 |
| **合计** | | **≈4.2 人日**（业务收敛后；E2E 与注册页不在本期） |

---

## 2. 架构总览

### 2.1 总体结构（两层守门）

```
【触发层：HTTP】
用户点击 AI 操作（上传/清洗/评估/洞察/提取/报告）
    ↓ FastAPI 依赖 require_llm_credential
    ├─ BYOK_ENABLED=false 或 ALLOW_SERVER_KEY_FALLBACK=true → 放行（记录 key_source='server'）
    ├─ 无凭据      → 428 LLM_CREDENTIAL_NOT_CONFIGURED（不发任何 LLM 请求、不入队）
    ├─ 凭据 invalid → 400 LLM_CREDENTIAL_INVALID
    └─ 正常 → 创建任务并入队（202）

【执行层：Celery worker】
BaseAgent.invoke(..., session, user_id)
    ↓ try 之前：按 user_id 解析凭据
    ├─ 有 Key → LLMClient(api_key=用户Key)   key_source='user'
    ├─ 无 Key 且 fallback=true → self.llm（服务端 Key）  key_source='server'
    └─ 无 Key 且 fallback=false → 抛 LLMCredentialNotConfiguredError（任务 failed，不发 LLM）
    ↓ 调用 LLM（含结构化输出 repair，同一凭据）
    ├─ 401/403 → mark_invalid（幂等）→ 任务 failed + 可读错误
    └─ 成功/失败 → CostTracker.track/record_failure（写 key_source）
                      ↓ key_source='user' 不纳入 DAILY_COST_LIMIT 降级统计
```

> **为什么不能只在 Agent 里守门**：5 条链路（清洗/评估/洞察/提取/报告）都由 Celery 异步执行，HTTP 先返回 202。428/400 属于"请求未被受理"，只能在 HTTP 层表达；worker 的前置检查是并发删除凭据时的兜底。

### 2.2 数据流（保存 Key）

```
前端 APIKeyModal
    ↓ PUT /api/v1/users/me/llm-credential { api_key: "sk-xxx", base_url: null, model: null }
路由 app/api/v1/llm_credential.py
    ↓ 语义校验：base_url 非空 → 400 LLM_CREDENTIAL_INVALID（SSRF 防护）
    ↓ 语义校验：长度 < 12 或非 sk- 前缀 → 400 LLM_CREDENTIAL_INVALID
    ↓ CredentialService.verify(api_key)  ← 真实调一次 LLM（max_tokens=1），不写 llm_calls
    ↓ 校验失败 → 400 LLM_CREDENTIAL_INVALID，不入库
    ↓ 通过 → CredentialEncryption.encrypt(api_key) → Fernet 密文
    ↓ UserLLMCredential upsert（user_id UNIQUE，覆盖更新）
    ↓ AuditLog（action=credential_configured，不含 Key）
    ↓ get_db 在请求边界 commit
    ↓ 返回 { byok_enabled, configured: true, key_hint: "sk-x…a1b2", status: "active", verified_at }
```

### 2.3 开关矩阵（后端行为）

| `BYOK_ENABLED` | `ALLOW_SERVER_KEY_FALLBACK` | Agent 行为 | 凭据 API | 前端入口 |
|---|---|---|---|---|
| `true` | `false`（生产） | 有 Key → 用户 Key；无 Key → **428** | 全部可用 | 显示 |
| `true` | `true`（本地/CI） | 有 Key → 用户 Key；无 Key → 服务端 Key | 全部可用 | 显示 |
| `false` | `false` | 服务端 Key（回退现状） | PUT/DELETE/verify → 404；GET → `{byok_enabled:false}` | 隐藏 |

> 判定顺序固定：**先 `BYOK_ENABLED`，再 `ALLOW_SERVER_KEY_FALLBACK`**。

### 2.4 文件清单

```
backend/
├── requirements.txt                           [改造] 显式声明 cryptography（当前仅间接依赖）
├── app/
│   ├── core/
│   │   ├── config.py                          [改造] +4 配置项 +SEED_DEMO_PASSWORD
│   │   ├── errors.py                          [改造] ErrorCode +3、ERROR_STATUS +3
│   │   ├── exceptions.py                      [改造] +3 异常类
│   │   ├── credential_encryption.py           [全新] Fernet 加解密 + key_hint
│   │   ├── cost_tracker.py                    [改造] track/record_failure +key_source；
│   │   │                                             get_daily_cost +only_server_key
│   │   └── redis.py                           [复用] 固定窗口限流用 get_redis()
│   ├── models/
│   │   ├── llm_credential.py                  [全新] UserLLMCredential ORM
│   │   ├── llm_call.py                        [改造] +key_source
│   │   └── __init__.py                        [改造] 注册新模型
│   ├── schemas/
│   │   └── llm_credential.py                  [全新] 入参/响应 Schema
│   ├── services/
│   │   └── credential_service.py              [全新] CRUD + verify + mark_invalid + 审计
│   ├── api/
│   │   ├── deps.py                            [改造] +require_llm_credential
│   │   └── v1/
│   │       ├── llm_credential.py              [全新] 4 个路由 + verify 限流
│   │       ├── __init__.py                    [改造] 注册路由（prefix="/users"）
│   │       ├── datasources.py                 [改造] upload/clean 挂守门
│   │       ├── analysis.py                    [改造] quality/insights 挂守门
│   │       ├── knowledge.py                   [改造] extract 挂守门
│   │       └── reports.py                     [改造] 创建报告挂守门
│   ├── agents/
│   │   └── base.py                            [改造] try 前解析凭据、agent_llm、401 处理、
│   │                                                   _track_success/_track_failure +key_source
│   └── （不新增 relationship，见 §3.5）
├── migrations/versions/
│   ├── 2026xxxx_<rev>_009_byok_credential_table.py   [全新] 建表 user_llm_credentials
│   ├── 2026xxxx_<rev>_010_llm_calls_key_source.py    [全新] llm_calls.key_source + 索引
│   └── 2026xxxx_<rev>_011_seed_demo_account.py       [全新] demo 账号（仅账号）
├── scripts/
│   └── seed_demo.py                           [全新] demo 业务数据（幂等 + --reset）
└── tests/
    ├── conftest.py                            [改造] autouse：ALLOW_SERVER_KEY_FALLBACK=True
    ├── unit/test_errors.py                    [改造] 28 条码 + 允许 428
    ├── unit/test_models_schema.py             [改造] 16 张表 + 新列断言
    ├── unit/test_credential_encryption.py     [全新]
    ├── integration/test_llm_credential_api.py [全新]
    ├── integration/test_byok_agent_injection.py [全新]
    └── security/test_byok_security.py         [全新]

frontend/
└── src/
    ├── api/
    │   ├── endpoints.js                       [改造] +llmCredential 2 条路径
    │   ├── client.js                          [改造] 428 `LLM_CREDENTIAL_NOT_CONFIGURED` → 打开凭据弹窗
    │   ├── llmCredential.js                   [全新] 3 个请求函数（verify 端点后端保留、前端不调）
    │   └── llmCredential.test.js              [全新]
    ├── hooks/
    │   ├── useLlmCredential.js                [全新] query/mutations + queryKey
    │   └── useLlmCredential.test.jsx          [全新]
    ├── lib/
    │   ├── errorMessages.js                   [改造] +3 条新码文案
    │   ├── errorMessages.test.js              [全新]
    │   ├── credentialGate.js                  [全新] zustand 弹窗状态（全局 428 触发）
    │   ├── credentialGate.test.js             [全新]
    │   ├── demoAccount.js                     [全新] 演示账号常量
    │   └── demoAccount.test.js                [全新]
    ├── components/
    │   ├── APIKeyModal/
    │   │   ├── APIKeyModal.jsx                [全新]
    │   │   ├── APIKeyModalHost.jsx            [全新] 全局宿主：读 credentialGate 状态渲染弹窗
    │   │   ├── index.js                       [全新]
    │   │   └── APIKeyModal.test.jsx           [全新]
    │   ├── layout/AppLayout.jsx               [改造] 挂 `<APIKeyModalHost />`
    │   └── layout/UserMenu.jsx                [改造] 增加「API Key 管理」+ 条件渲染
    └── pages/
        └── Login/index.jsx                    [改造] 演示账号展示 + 点击预填
    e2e/
    └── byok.spec.js                           [延后] Phase 2 参考稿（本期不实现）
```

---

## 3. M1：契约 + 存储层 + 加密服务 + 凭据 API

### 3.1 M0 契约（必须先做，不可跳过）

项目规则：**错误码严格取自 API 设计 §12.2，不得自造**。因此按以下顺序改文档，再改代码：

1. `docs/03-architecture/04-API设计.md`
   - §12.1 增补 `428`（请求需要先满足前置条件：未配置 LLM 凭据）
   - §12.2 增补 3 条码：`LLM_CREDENTIAL_NOT_CONFIGURED`(428)、`LLM_CREDENTIAL_INVALID`(400)、`LLM_CREDENTIAL_DECRYPT_FAILED`(500)
   - 新增「BYOK 凭据」端点章节（4 个端点 + 请求/响应/错误）
2. `docs/03-architecture/03-数据库设计.md`
   - 新表 `user_llm_credentials` DDL、`llm_calls.key_source`、审计 action 说明
3. `docs/01-requirements/04-需求-用户自带LLM-API-Key（BYOK）.md`
   - §6 标题、§13、§16 的"迁移 008"改为 **009/010/011**（008 已被 `llm_calls_datasource_set_null` 占用）
4. `docs/05-design/03-页面设计规范.md`：API Key Modal、未配置引导、演示账号提示

### 3.2 config.py — 新增配置项

在 `Settings` 类中、`@lru_cache def get_settings()` 之前追加：

```python
    # ---------------- BYOK：用户自带 LLM API Key ----------------
    # 总开关；false 时忽略用户凭据、隐藏设置入口（回退现状：服务端 Key）
    BYOK_ENABLED: bool = True

    # 32 字节 base64 Fernet 密钥；缺失或格式非法时拒绝保存/解密（fail closed，不退化为明文）
    # 生成：python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # 生产：通过 Secrets Manager / 平台密钥注入，不得写入代码仓库或镜像
    CREDENTIAL_ENCRYPTION_KEY: str = ""

    # 仅开发/CI/E2E：无用户 Key 时回退服务端 DEEPSEEK_API_KEY；生产必须 false
    ALLOW_SERVER_KEY_FALLBACK: bool = False

    # verify 端点限流（次/分钟/用户）
    LLM_CREDENTIAL_VERIFY_PER_MINUTE: int = 5

    # demo 账号种子密码（迁移 011 使用；生产通过密钥注入覆盖）
    SEED_DEMO_PASSWORD: str = "demo123"
```

同步 `backend/.env.example`（该文件头部声明"是配置项事实源，必须与 `config.py` 一一对应"）；`.env.production.example` 同步补生产值说明（`ALLOW_SERVER_KEY_FALLBACK=false`、密钥来自 Secrets Manager）：

```ini
# ── BYOK：用户自带 LLM API Key ─────────────────────────────
BYOK_ENABLED=true
# 32 字节 base64；缺失时拒绝保存（fail closed）
# 生成：python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
CREDENTIAL_ENCRYPTION_KEY=
# 仅开发/CI/E2E 开启；生产必须 false
ALLOW_SERVER_KEY_FALLBACK=false
LLM_CREDENTIAL_VERIFY_PER_MINUTE=5
# demo 账号密码（迁移 011 使用；生产请覆盖）
SEED_DEMO_PASSWORD=demo123
```

> **必须同步测试环境（否则存量用例回归失败）**：默认 `ALLOW_SERVER_KEY_FALLBACK=False`，而现有集成用例（`test_upload_clean.py`、`test_evaluation_api.py`、`test_insight_api.py`、`test_knowledge_api.py`、`test_reports_api.py`、`test_e2e.py` 等 6 处）都用**无凭据**的 `test_user` 打被守门端点并断言 202。不做下面任一步，这些用例会集体变成 428：
>
> 1. `backend/tests/conftest.py` 增加 autouse fixture（推荐，一行开关即可让存量用例行为不变）：
>
> ```python
> @pytest.fixture(autouse=True)
> def allow_server_key_fallback_in_tests(monkeypatch) -> None:
>     """测试环境默认允许回退服务端 Key（BYOK 守门用例自行改回 False）。"""
>     monkeypatch.setattr(settings, "ALLOW_SERVER_KEY_FALLBACK", True)
> ```
>
> 2. CI 的 `test.yml` / `e2e.yml` 显式注入 `ALLOW_SERVER_KEY_FALLBACK: "true"`、`CREDENTIAL_ENCRYPTION_KEY`（E2E 与后端服务都要）。
> 3. BYOK 专项用例（428 断言）在用例内 `monkeypatch.setattr(settings, "ALLOW_SERVER_KEY_FALLBACK", False)`。

### 3.3 errors.py / exceptions.py — 错误码与异常类

`backend/app/core/errors.py`：在 429 段之后追加 3 条业务码，并在 `ERROR_STATUS` 登记：

```python
class ErrorCode(str, Enum):
    ...
    # 428 / 400 / 500（BYOK，需求 §7）
    LLM_CREDENTIAL_NOT_CONFIGURED = "LLM_CREDENTIAL_NOT_CONFIGURED"
    LLM_CREDENTIAL_INVALID = "LLM_CREDENTIAL_INVALID"
    LLM_CREDENTIAL_DECRYPT_FAILED = "LLM_CREDENTIAL_DECRYPT_FAILED"


ERROR_STATUS[ErrorCode.LLM_CREDENTIAL_NOT_CONFIGURED] = 428
ERROR_STATUS[ErrorCode.LLM_CREDENTIAL_INVALID] = 400
ERROR_STATUS[ErrorCode.LLM_CREDENTIAL_DECRYPT_FAILED] = 500
```

`backend/app/core/exceptions.py`：追加 3 个子类（class 级 `code`，业务代码只抛子类、不传 `status_code`），并加入 `__all__`：

```python
class LLMCredentialNotConfiguredError(AIInsightHubException):
    """未配置用户 Key 且未开启 fallback（428）。"""

    code = ErrorCode.LLM_CREDENTIAL_NOT_CONFIGURED
    default_message = "请先配置您的 DeepSeek API Key"


class LLMCredentialInvalidError(AIInsightHubException):
    """Key 格式非法 / 连通性校验失败 / 已标记 invalid（400）。"""

    code = ErrorCode.LLM_CREDENTIAL_INVALID
    default_message = "API Key 无效或已失效，请更新后再试"


class LLMCredentialDecryptError(AIInsightHubException):
    """加密密钥缺失/非法，或密文无法解密（500）。"""

    code = ErrorCode.LLM_CREDENTIAL_DECRYPT_FAILED
    default_message = "凭据解密失败，加密密钥可能已更换"
```

> 不要使用 `AIInsightHubException(error_code=...)`（不存在该参数），也不要用 `HTTPException(detail={...})` 携带业务码——统一 handler 会丢掉 dict detail。

**必须同步存量契约测试**（否则 M1 门禁直接红）——`backend/tests/unit/test_errors.py`：

```python
# 1) BUSINESS_CODES 集合追加 3 条
# 2) assert len(ErrorCode) == 25  → 28
# 3) 状态白名单加入 428：
assert set(ERROR_STATUS.values()) <= {400, 401, 403, 404, 409, 413, 415, 422, 428, 429, 500}
# 4) test_exception_classes_map_to_business_codes 的 allowed 集合同样加入 428
```

同时把这 3 条码补进 `docs/03-architecture/04-API设计.md` §12.2 表格（"25 条"的描述也要改）。

### 3.4 加密服务

`backend/app/core/credential_encryption.py`（全新）：

```python
"""凭据加解密服务。

安全约束：
- 密钥缺失/格式非法 → 抛 LLMCredentialDecryptError（fail closed，不退化为明文）；
- decrypt 失败（密钥不匹配/密文损坏）→ 同一错误类，调用方返回 500；
- key_hint 固定格式：前 5 位 + `…` + 后 4 位（调用前已保证 len >= 12）。
"""
from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings
from app.core.exceptions import LLMCredentialDecryptError


def _get_fernet() -> Fernet:
    key = settings.CREDENTIAL_ENCRYPTION_KEY
    if not key:
        raise LLMCredentialDecryptError("CREDENTIAL_ENCRYPTION_KEY 未配置，无法保存或读取凭据")
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError) as exc:
        raise LLMCredentialDecryptError("CREDENTIAL_ENCRYPTION_KEY 格式非法（需 32 字节 base64）") from exc


def encrypt(plaintext: str) -> str:
    """加密明文 Key，返回 Fernet 密文（base64 字符串）。"""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """解密密文；失败抛 LLMCredentialDecryptError。"""
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise LLMCredentialDecryptError("凭据解密失败，加密密钥可能已更换") from exc


def make_hint(api_key: str) -> str:
    """展示用掩码：前 5 位 + `…` + 后 4 位（如 sk-x…a1b2）。"""
    return f"{api_key[:5]}…{api_key[-4:]}"


def ensure_encryption_ready() -> None:
    """保存前快速失败：密钥缺失/非法时此处即抛 500，避免先花一次 verify 的调用成本。"""
    _get_fernet()
```

> `cryptography` 必须显式加入 `backend/requirements.txt`（当前仅由 `python-jose[cryptography]` 间接带入，不可依赖）。

### 3.5 模型

`backend/app/models/llm_credential.py`（全新）：

```python
"""UserLLMCredential ORM 模型（一个用户最多一条有效凭据）。"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UserLLMCredential(Base):
    """用户 LLM 凭据表（密文存储）。"""

    __tablename__ = "user_llm_credentials"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'invalid')", name="status_valid"),
        Index(
            "uk_user_llm_credentials_user_id",
            "user_id",
            unique=True,
        ),
        Index("idx_user_llm_credentials_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default=text("'deepseek'")
    )
    # Phase 1：保存时非空即拒绝（SSRF 防护）；Phase 2 开放时须加 URL 白名单
    base_url: Mapped[str | None] = mapped_column(String(500))
    model: Mapped[str | None] = mapped_column(String(100))  # Phase 2 预留
    encrypted_api_key: Mapped[str] = mapped_column(Text, nullable=False)
    # 固定格式：前 5 位 + … + 后 4 位
    key_hint: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'active'")
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=text("NOW()"))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=text("NOW()"))
```

`backend/app/models/__init__.py` 追加（**必须登记**，否则 Alembic autogenerate 看不到该表）：

```python
from app.models.llm_credential import UserLLMCredential
# __all__ 中追加 "UserLLMCredential"
```

> **必须同步模型契约测试**：`backend/tests/unit/test_models_schema.py` 精确断言表集合与数量（`EXPECTED_TABLES` / `len(...) == 15`），加表后需改为 16 并补 `user_llm_credentials` 的列断言；`app/models/__init__.py` 文件头注释的"15 张表"也要一并更新。

> **不新增 `User.llm_credential` relationship**。原因：① `User` 当前没有任何 relationship，`users` 与凭据表由 DB 外键 + 凭据服务直接查询已足够；② SQLAlchemy 2.0 异步下访问未 eager-load 的 relationship 会触发 `MissingGreenlet`，多一处 lazy 关系就多一处踩坑点。若后续确需（如级联展示），必须 `lazy="selectin"` 并在查询中显式 eager load。

### 3.6 迁移 009 / 010

> **实际落地拆分**（与本文早期版本不同）：**009 只建表**；`llm_calls.key_source` 单独放 **010**；demo 账号放 **011**（见 §6.1）。下方 009 代码保留为建表参考，`key_source` 见紧随其后的 010 片段。

用 Alembic 生成（文件名符合 `alembic.ini` 的 `file_template`）：

```bash
cd backend
alembic revision -m "009 byok credential table"
# 产出 migrations/versions/2026xxxx_HHMM_<rev>_009_byok_credential_table.py
```

填入：

```python
"""009 byok credential table

Revision ID: <生成值>
Revises: 9b2d4f6a8c1e    # 008
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = "<生成值>"
down_revision: str | None = "9b2d4f6a8c1e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_llm_credentials",
        sa.Column(
            "id", PG_UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id", PG_UUID(as_uuid=True),
            # 约束名必须与 metadata 命名约定一致（ck/uk/fk/ix），否则 autogenerate 会持续产生 diff
            sa.ForeignKey(
                "users.id",
                ondelete="CASCADE",
                name=op.f("fk_user_llm_credentials_user_id_users"),
            ),
            nullable=False,
        ),
        sa.Column("provider", sa.String(50), nullable=False, server_default="deepseek"),
        sa.Column("base_url", sa.String(500), nullable=True),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("encrypted_api_key", sa.Text, nullable=False),
        sa.Column("key_hint", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("verified_at", sa.DateTime, nullable=True),
        # 与既有表风格一致：模型侧 Optional + 迁移侧 nullable=True + server_default NOW()
        sa.Column("created_at", sa.DateTime, server_default=sa.text("NOW()"), nullable=True),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("NOW()"), nullable=True),
        sa.CheckConstraint(
            "status IN ('active', 'invalid')",
            name=op.f("ck_user_llm_credentials_status_valid"),
        ),
    )
    op.create_index(
        "uk_user_llm_credentials_user_id",
        "user_llm_credentials",
        ["user_id"],
        unique=True,
    )
    op.create_index(
        "idx_user_llm_credentials_status", "user_llm_credentials", ["status"]
    )

    # llm_calls.key_source：存量记录默认 'server'（不写业务回填逻辑）
    op.add_column(
        "llm_calls",
        sa.Column("key_source", sa.String(10), nullable=False, server_default="server"),
    )
    # 降级统计按 (key_source, created_at) 聚合，加复合索引
    op.create_index(
        "idx_llm_calls_key_source_date", "llm_calls", ["key_source", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("idx_llm_calls_key_source_date", table_name="llm_calls")
    op.drop_column("llm_calls", "key_source")
    op.drop_index("idx_user_llm_credentials_status", table_name="user_llm_credentials")
    op.drop_index("uk_user_llm_credentials_user_id", table_name="user_llm_credentials")
    op.drop_table("user_llm_credentials")
```

验证（**双向**）：

```bash
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

**010：`llm_calls.key_source`（成本隔离字段）**

```python
"""010 llm_calls key_source"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "<生成值>"
down_revision: Union[str, None] = "<009 的 revision>"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "llm_calls",
        sa.Column("key_source", sa.String(length=10), server_default="server", nullable=False),
    )
    op.create_index(
        "idx_llm_calls_key_source_date", "llm_calls", ["key_source", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("idx_llm_calls_key_source_date", table_name="llm_calls")
    op.drop_column("llm_calls", "key_source")
```

`backend/app/models/llm_call.py` 同步加字段（与迁移一致）：

```python
key_source: Mapped[str] = mapped_column(
    String(10), nullable=False, server_default=text("'server'")
)
```

### 3.7 Pydantic Schema

`backend/app/schemas/llm_credential.py`（全新）：

```python
"""BYOK 凭据 Schema（API 设计「BYOK 凭据」）。"""
from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.base import BaseSchema


class CredentialIn(BaseSchema):
    """PUT 保存 / POST verify 共用的请求体。

    只做类型与长度上限约束；语义校验（sk- 前缀、base_url 拒绝）在路由层统一返回 400，
    避免 Pydantic 校验失败被统一 handler 转成 422。
    """

    api_key: str = Field(max_length=256)
    base_url: str | None = None   # Phase 1：非空即拒绝
    model: str | None = None      # Phase 2 预留，当前忽略


class CredentialStatusResponse(BaseSchema):
    """GET/PUT 响应（不含明文/密文）。"""

    byok_enabled: bool = True
    configured: bool
    provider: str | None = None
    key_hint: str | None = None
    status: str | None = None
    verified_at: datetime | None = None


class VerifyResponse(BaseSchema):
    valid: bool
```

### 3.8 凭据服务

`backend/app/services/credential_service.py`（全新）：

```python
"""凭据服务（user_llm_credentials 唯一读写入口）。

职责：
- get_active：给 Agent 用，返回解密后的明文 Key 或 None（解密失败 → 500 错误类）
- get_active_credential：给 HTTP 守门用，返回 ORM 行（判 status，不解密）
- decrypt_credential：把已取到的 ORM 行解密成明文（避免重复查库）
- get_status：查询状态（不含明文/密文）
- upsert / delete：保存/删除（幂等）
- verify：连通性测试（不写 llm_calls）
- mark_invalid：幂等标记失效（并发安全）
- _write_audit：写审计（不含 Key 值）
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.credential_encryption import decrypt, encrypt, make_hint
from app.core.llm import LLMClient, LLMError
from app.models.llm_credential import UserLLMCredential
from app.models.security import AuditLog

# 审计 action（需求 §5 / FR-BK-18）
AUDIT_CREDENTIAL_CONFIGURED = "credential_configured"
AUDIT_CREDENTIAL_DELETED = "credential_deleted"
AUDIT_CREDENTIAL_INVALID = "credential_invalid"


def _now_naive() -> datetime:
    """统一写库时间（项目 DateTime 列无时区；asyncpg 拒收 aware datetime）。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class CredentialService:
    """用户凭据服务。"""

    # -- 读取 ---------------------------------------------------------
    async def get_active_credential(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> UserLLMCredential | None:
        """返回 ORM 行（不解密），供守门判断 status。"""
        result = await session.execute(
            select(UserLLMCredential).where(UserLLMCredential.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_active(self, session: AsyncSession, user_id: uuid.UUID) -> str | None:
        """返回解密后的明文 Key；未配置返回 None；解密失败抛 LLMCredentialDecryptError。"""
        credential = await self.get_active_credential(session, user_id)
        if credential is None or credential.status != "active":
            return None
        return decrypt(credential.encrypted_api_key)

    @staticmethod
    def decrypt_credential(credential: UserLLMCredential) -> str:
        """解密已取到的凭据行（避免 Agent 侧重复查库；解密失败抛 LLMCredentialDecryptError）。"""
        return decrypt(credential.encrypted_api_key)

    async def get_status(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> dict | None:
        credential = await self.get_active_credential(session, user_id)
        if credential is None:
            return None
        return {
            "configured": True,
            "provider": credential.provider,
            "key_hint": credential.key_hint,
            "status": credential.status,
            "verified_at": credential.verified_at,
        }

    # -- 写入 ---------------------------------------------------------
    async def upsert(
        self, session: AsyncSession, user_id: uuid.UUID, api_key: str
    ) -> dict:
        """保存/更新（调用前已完成 verify）；返回状态信息。"""
        encrypted = encrypt(api_key)
        hint = make_hint(api_key)
        now = _now_naive()

        credential = await self.get_active_credential(session, user_id)
        if credential is None:
            credential = UserLLMCredential(
                user_id=user_id,
                encrypted_api_key=encrypted,
                key_hint=hint,
                status="active",
                verified_at=now,
            )
            session.add(credential)
        else:
            credential.encrypted_api_key = encrypted
            credential.key_hint = hint
            credential.status = "active"
            credential.verified_at = now
            credential.updated_at = now

        self._write_audit(session, user_id, AUDIT_CREDENTIAL_CONFIGURED)
        await session.flush()   # commit 由 get_db 在请求边界统一执行
        return {
            "byok_enabled": True,
            "configured": True,
            "provider": credential.provider,
            "key_hint": hint,
            "status": "active",
            "verified_at": now,
        }

    async def delete(self, session: AsyncSession, user_id: uuid.UUID) -> None:
        """删除凭据；不存在时静默成功（幂等）。"""
        credential = await self.get_active_credential(session, user_id)
        if credential is None:
            return
        await session.delete(credential)
        self._write_audit(session, user_id, AUDIT_CREDENTIAL_DELETED)

    async def mark_invalid(self, session: AsyncSession, user_id: uuid.UUID) -> None:
        """幂等标记 invalid：WHERE status != 'invalid'（并发任务只生效一次）。"""
        result = await session.execute(
            update(UserLLMCredential)
            .where(
                UserLLMCredential.user_id == user_id,
                UserLLMCredential.status != "invalid",
            )
            .values(status="invalid", updated_at=_now_naive())
        )
        # 只有真正发生状态迁移才写审计，避免并发任务重复记录
        if result.rowcount:
            self._write_audit(session, user_id, AUDIT_CREDENTIAL_INVALID)

    # -- 连通性校验 ---------------------------------------------------
    async def verify(self, api_key: str) -> bool:
        """真实调一次 LLM（max_tokens=1）验证 Key 可用；不写 llm_calls、不计成本。

        `LLMError` 覆盖 401/403（鉴权）、402（余额不足）、429（限流）、400（参数）、5xx，
        验证语义下都视为"不可用"；不用 `BaseException`，避免吞掉编程错误。
        """
        try:
            async with LLMClient(api_key=api_key) as client:
                await client.chat(
                    messages=[{"role": "user", "content": "hi"}],
                    max_tokens=1,
                )
            return True
        except LLMError:
            return False

    # -- 内部 ---------------------------------------------------------
    @staticmethod
    def _write_audit(session: AsyncSession, user_id: uuid.UUID, action: str) -> None:
        """审计日志（resource_id 为 UUID 列，details 不含任何 Key 信息）。"""
        session.add(
            AuditLog(
                user_id=user_id,
                action=action,
                resource_type="llm_credential",
                resource_id=user_id,
                details={},
            )
        )


credential_service = CredentialService()
```

> 说明：`LLMError` 是 LLM 异常族基类，已覆盖 401/403/402/429/400/5xx；**不要**改成 `except Exception`——那会吞掉 `MissingGreenlet` 之类编程错误，让"Key 不可用"和"代码写错"混为一谈。

### 3.9 凭据路由（4 个 API）

`backend/app/api/v1/llm_credential.py`（全新）：

```python
"""BYOK 凭据接口（API 设计「BYOK 凭据」）。

PUT    /users/me/llm-credential          保存（强制 verify，失败不入库）
GET    /users/me/llm-credential          查询状态
DELETE /users/me/llm-credential          删除
POST   /users/me/llm-credential/verify   连通性测试（限流）
"""
from __future__ import annotations

import re
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.core.config import settings
from app.core.credential_encryption import ensure_encryption_ready
from app.core.database import get_db
from app.core.exceptions import LLMCredentialInvalidError, RateLimitExceededError
from app.core.redis import get_redis
from app.models.user import User
from app.schemas.llm_credential import (
    CredentialIn,
    CredentialStatusResponse,
    VerifyResponse,
)
from app.services.credential_service import credential_service

router = APIRouter(prefix="/me/llm-credential")

# DeepSeek Key：sk- 开头，至少 12 位
_KEY_RE = re.compile(r"^sk-[A-Za-z0-9]{9,}$")


def _ensure_enabled() -> None:
    if not settings.BYOK_ENABLED:
        raise HTTPException(status_code=404, detail="BYOK is not enabled")


def _validate_payload(body: CredentialIn) -> None:
    """Phase 1 语义校验：统一 400 LLM_CREDENTIAL_INVALID（不用 Pydantic 校验，避免 422）。"""
    if body.base_url is not None and body.base_url.strip():
        raise LLMCredentialInvalidError("Phase 1 不支持自定义端点（base_url 必须为空）")
    if len(body.api_key) < 12 or not _KEY_RE.match(body.api_key):
        raise LLMCredentialInvalidError("api_key 格式不符合要求（需 sk- 开头且长度足够）")


async def _enforce_verify_rate_limit(user_id: uuid.UUID) -> None:
    """verify 端点限流：固定窗口 ≤ LLM_CREDENTIAL_VERIFY_PER_MINUTE 次/分钟/用户。"""
    window = int(time.time() // 60)
    key = f"byok:verify:{user_id}:{window}"
    redis = get_redis()
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, 60)
    if count > settings.LLM_CREDENTIAL_VERIFY_PER_MINUTE:
        reset_at = (window + 1) * 60
        raise RateLimitExceededError(
            "Too many verify requests",
            headers={"Retry-After": str(max(1, reset_at - int(time.time())))},
        )


@router.put("", response_model=CredentialStatusResponse, response_model_by_alias=False)
async def save_credential(
    body: CredentialIn,
    user: User = Depends(require_roles("admin", "user")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """保存/更新凭据：强制连通性校验，失败不落库。"""
    _ensure_enabled()
    ensure_encryption_ready()   # 密钥缺失/非法时先失败，不浪费一次 verify
    _validate_payload(body)
    if not await credential_service.verify(body.api_key):
        raise LLMCredentialInvalidError("API Key 连通性校验失败，请确认 Key 正确且账户有余额")
    return await credential_service.upsert(session, user.id, body.api_key)


@router.get("", response_model=CredentialStatusResponse, response_model_by_alias=False)
async def get_credential_status(
    user: User = Depends(require_roles("admin", "user", "viewer")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """查询自身凭据状态（不含明文/密文）。viewer 也可查看。"""
    if not settings.BYOK_ENABLED:
        return {"byok_enabled": False, "configured": False}
    status_data = await credential_service.get_status(session, user.id)
    if status_data is None:
        return {"byok_enabled": True, "configured": False}
    return {**status_data, "byok_enabled": True}


@router.delete("", status_code=204)
async def delete_credential(
    user: User = Depends(require_roles("admin", "user")),
    session: AsyncSession = Depends(get_db),
) -> None:
    """删除凭据（幂等）；删除后 AI 操作恢复 428。"""
    _ensure_enabled()
    await credential_service.delete(session, user.id)


@router.post("/verify", response_model=VerifyResponse, response_model_by_alias=False)
async def verify_credential(
    body: CredentialIn,
    user: User = Depends(require_roles("admin", "user")),
) -> dict:
    """独立连通性测试（限流）。前端主流程使用"验证并保存"，本端点供后续"重新验证"使用。"""
    _ensure_enabled()
    _validate_payload(body)
    await _enforce_verify_rate_limit(user.id)
    if not await credential_service.verify(body.api_key):
        raise LLMCredentialInvalidError("API Key 无效或账户无余额")
    return {"valid": True}
```

注册到 `backend/app/api/v1/__init__.py`（`include_router` 的前缀在前，最终路径 = `/users` + `/me/llm-credential`）：

```python
from app.api.v1 import (..., llm_credential, ...)

router.include_router(llm_credential.router, prefix="/users", tags=["凭据"])
```

> 4 个端点均固定操作 `current_user`，不接受任何 user_id 参数——这是"admin 也读不到他人凭据"的结构性保证（AC-BK-05 按此验收）。

### 3.10 M1 门禁

```bash
cd backend
pytest tests/unit/test_credential_encryption.py \
       tests/integration/test_llm_credential_api.py -v
black --check app tests && flake8 app tests && mypy app
```

- 覆盖：加密往返、掩码格式、密钥缺失/格式非法、密文损坏、4 个 API 的 CRUD、base_url 400、verify 400、限流 429、审计无明文
- 迁移双向验证通过

---

## 4. M2：HTTP 守门 + Agent 注入 + 成本隔离

### 4.1 HTTP 守门依赖

`backend/app/api/deps.py` 追加（`Depends` / `get_db` / `AsyncSession` / `User` 该文件已导入，只需补下面 4 个 import）：

```python
from app.core.config import settings
from app.core.exceptions import LLMCredentialInvalidError, LLMCredentialNotConfiguredError
from app.services.credential_service import credential_service


async def require_llm_credential(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> User:
    """BYOK 守门（AI 触发端点专用）。

    - BYOK 关闭或允许回退服务端 Key → 直接放行（行为与现状一致）；
    - 无凭据 → 428 LLM_CREDENTIAL_NOT_CONFIGURED（不入队、不发 LLM）；
    - 凭据已标记 invalid → 400 LLM_CREDENTIAL_INVALID（引导更新）。
    """
    if not settings.BYOK_ENABLED or settings.ALLOW_SERVER_KEY_FALLBACK:
        return user
    credential = await credential_service.get_active_credential(session, user.id)
    if credential is None:
        raise LLMCredentialNotConfiguredError()
    if credential.status == "invalid":
        raise LLMCredentialInvalidError()
    return user
```

> `get_db` 与路由内 `Depends(get_db)` 命中 FastAPI 依赖缓存，是**同一个请求级 session**，不会多开连接；提交仍由 `get_db` 在请求边界统一执行。别忘了把 `require_llm_credential` 加入 deps.py 的 `__all__`。

### 4.2 挂载到 6 个触发端点

| 端点 | 文件:行 | 说明 |
|---|---|---|
| `POST /datasources/{id}/upload` | `app/api/v1/datasources.py:152` | 上传后自动入队清洗，必须守门 |
| `POST /datasources/{id}/clean` | `app/api/v1/datasources.py:251` | 清洗 |
| `POST /datasources/{id}/analyze/quality` | `app/api/v1/analysis.py:38` | 质量评估 |
| `POST /datasources/{id}/analyze/insights` | `app/api/v1/analysis.py:142` | 洞察 |
| `POST /datasources/{id}/extract-knowledge` | `app/api/v1/knowledge.py:31` | 知识提取 |
| `POST /datasources/{id}/reports` | `app/api/v1/reports.py:29` | 报告生成 |

统一用依赖挂载，**不要**在每个 handler 里重复判断：

```python
from fastapi import APIRouter, Depends
from app.api.deps import require_llm_credential, require_roles

@router.post(
    "/{datasource_id}/clean",
    ...,
    dependencies=[Depends(require_llm_credential)],
)
async def trigger_clean(...):
    ...
```

> 为什么不在 `invoke` 里抛 428：见 §2.1。5 条链路都是 Celery 异步，HTTP 已返回 202，`invoke` 内的异常会被 `except Exception` 收敛成 `AgentResult(success=False)` 或任务 failed。

### 4.3 BaseAgent.invoke 改造

`backend/app/agents/base.py`。三个改动点：

**(1) `try` 之前解析凭据**（异常必须能冒泡到 worker 任务层）：

```python
    async def invoke(
        self,
        input_data: Mapping[str, Any],
        *,
        session: AsyncSession | None = None,
        task_id: uuid.UUID | str | None = None,
        user_id: uuid.UUID | None = None,
        datasource_id: uuid.UUID | None = None,
    ) -> AgentResult:
        started = time.perf_counter()
        model = self.config.model
        level = DegradationLevel.NORMAL
        attempts = 0
        token_usage = {"input": 0, "output": 0}
        guard_hits: list[str] = []

        # ── BYOK：解析本次调用使用的凭据（必须在 try 之外，异常向上冒泡） ──
        # 注：延迟 import，避免 agents 与 services 的模块级循环依赖
        key_source = "server"
        agent_llm = self.llm
        if settings.BYOK_ENABLED and user_id is not None and session is not None:
            from app.services.credential_service import credential_service

            credential = await credential_service.get_active_credential(session, user_id)
            # 已标记失效：绝不回退服务端 Key（FR-BK-09）
            if credential is not None and credential.status != "active":
                raise LLMCredentialInvalidError()
            if credential is not None:
                agent_llm = LLMClient(
                    model=self.config.model,
                    timeout=self.config.timeout,
                    api_key=credential_service.decrypt_credential(credential),
                )
                key_source = "user"
            elif not settings.ALLOW_SERVER_KEY_FALLBACK:
                raise LLMCredentialNotConfiguredError()
        # ── END BYOK ──

        try:
            ...
```

> - `session is None`（POC/单测）时保持现状走 `self.llm`；
> - `decrypt_credential` 解密失败会抛 `LLMCredentialDecryptError`（500），任务 failed 并提示"密钥可能已更换"，绝不退化为明文或静默用服务端 Key。

**(2) LLM 调用与结构化 repair 都用 `agent_llm`**：

```python
            async def _call(attempt: int) -> LLMResponse:
                nonlocal attempts
                attempts = attempt
                response = await agent_llm.chat(          # ← 原来是 self.llm.chat
                    messages,
                    model=model,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                )
                ...
            response = await async_retry(_call, config=retry_config, guard=guard)

            payload: Any = response.content
            if self.output_schema is not None:
                payload = await _parse_structured(
                    self.output_schema,
                    text=response.content,
                    llm=agent_llm,                     # ← 原来是 self.llm（FR-BK-11 要求 repair 复用同一凭据）
                    usage_collector=repair_usage,
                )
```

**(3) 鉴权失败：标记 invalid + 可读错误**。在 `except Exception` 分支内、写失败记录之后判定：

```python
        except Exception as exc:  # noqa: BLE001 - 对外统一收敛
            duration = time.perf_counter() - started
            logger.opt(exception=exc).warning(
                "agent execution failed agent={} error={}",
                self.config.name,
                type(exc).__name__,
            )
            await self._track_failure(
                session,
                error=exc,
                model=model,
                task_id=task_id,
                attempt=attempts,
                user_id=user_id,
                datasource_id=datasource_id,
                duration=duration,
                key_source=key_source,
            )

            # ── BYOK：用户 Key 失效 → 幂等标记 invalid，抛可读错误（不回退服务端 Key） ──
            if (
                isinstance(exc, LLMAuthenticationError)
                and key_source == "user"
                and session is not None
                and user_id is not None
            ):
                from app.services.credential_service import credential_service

                await credential_service.mark_invalid(session, user_id)
                await session.flush()   # 不手动 commit：由任务入口统一提交（如 cleaning_service._execute_clean 的 except 分支）
                record_agent_invocation(
                    agent=self.config.name, status="failed", duration_seconds=duration
                )
                raise LLMCredentialInvalidError() from exc

            record_agent_invocation(
                agent=self.config.name, status="failed", duration_seconds=duration
            )
            return AgentResult(
                success=False,
                metadata={...},
                errors=[f"{type(exc).__name__}: {exc}"],
                ...
            )
```

> 注意 `_track_failure` 抛出的失败记录同样带 `key_source`，避免把用户 Key 的失败计成服务端 Key 调用。

> **对 D-01（"异常一律收敛为 `AgentResult`，不向调用方抛出"）的显式例外**：BYOK 引入的两类异常必须向上抛——`LLMCredentialNotConfiguredError`（`try` 之前，属于"前置条件不满足"）与 `LLMCredentialInvalidError`（鉴权失败，属于"凭据失效"）。它们不是 Agent 执行失败，而是不能继续执行的前置错误；worker 任务入口会把它们落成 `task.status='failed'` + 可读 message，HTTP 守门则在触发时生效。请在 `base.py` 模块 docstring 的 D-01 说明中补一行"BYOK 凭据错误除外"，避免后人误改回吞异常。

> 文件顶部需补 import：`from app.core.exceptions import LLMCredentialInvalidError, LLMCredentialNotConfiguredError`、`from app.core.llm import LLMAuthenticationError`（现有 import 行是 `LLMClient, LLMResponse, LLMUsage, Message`，要一起补）。

### 4.4 CostTracker 改造（`llm_calls` 唯一写入口）

`backend/app/core/cost_tracker.py` 四处：

**(1) `track` 增加 `key_source` 参数并写库**：

```python
    async def track(
        self,
        *,
        response: LLMResponse,
        service: str = _DEFAULT_SERVICE,
        task_id: uuid.UUID | str | None = None,
        attempt: int = 0,
        user_id: uuid.UUID | None = None,
        datasource_id: uuid.UUID | None = None,
        agent_name: str | None = None,
        agent_version: str | None = None,
        key_source: str = "server",          # ← 新增
    ) -> LlmCall:
        ...
        values: dict[str, Any] = {
            ...,
            "status": "success",
            "error_type": None,
            "error_message": None,
            "key_source": key_source,        # ← 新增
        }
```

**(2) `record_failure` 同样新增参数与字段**（失败行也要有来源，审计口径才不串）：

```python
    async def record_failure(
        self,
        *,
        error: BaseException,
        model: str,
        service: str = _DEFAULT_SERVICE,
        task_id: uuid.UUID | str | None = None,
        attempt: int = 0,
        user_id: uuid.UUID | None = None,
        datasource_id: uuid.UUID | None = None,
        agent_name: str | None = None,
        agent_version: str | None = None,
        duration_seconds: float | None = None,
        key_source: str = "server",          # ← 新增
    ) -> LlmCall:
        values = {
            ...,
            "status": "failed",
            "key_source": key_source,        # ← 新增
        }
```

**(3) `_upsert` 的 `update_fields` 追加 `"key_source"`**（幂等重试回写时会同步更新）。

**(4) `get_daily_cost` 增加成本隔离参数**：

```python
    async def get_daily_cost(
        self,
        *,
        user_id: uuid.UUID | None = None,
        now: datetime | None = None,
        only_server_key: bool = True,        # ← 新增：降级只统计服务端 Key
    ) -> Decimal:
        """当日（UTC）成功调用成本合计；默认仅统计服务端 Key（BYOK 成本隔离）。"""
        stmt = select(func.coalesce(func.sum(LlmCall.total_cost), 0)).where(
            LlmCall.status == "success",
            LlmCall.created_at >= _day_start(now),
        )
        if only_server_key:
            stmt = stmt.where(LlmCall.key_source == "server")
        if user_id is not None:
            stmt = stmt.where(LlmCall.user_id == user_id)
        value = await self._session.scalar(stmt)
        return Decimal(str(value or 0)).quantize(_COST_QUANT)
```

> - `DegradationManager.get_cost_ratio()` **无需修改**（默认 `only_server_key=True` 即生效）；
> - `get_usage_stats()`（用量报表）**不要过滤**，用户 Key 的估算成本仍应展示。

### 4.5 `_track_success` / `_track_failure` 传参

`backend/app/agents/base.py` 两个私有方法各加一个 `key_source: str = "server"` 参数，并在内部透传给 `CostTracker`：

```python
    async def _track_success(
        self, session, *, usage, model, task_id, attempt, user_id, datasource_id,
        duration, key_source: str = "server",
    ) -> None:
        ...
        await CostTracker(session).track(
            response=synthetic,
            task_id=task_id,
            attempt=attempt,
            user_id=user_id,
            datasource_id=datasource_id,
            agent_name=self.config.name,
            agent_version=self.config.version,
            key_source=key_source,          # ← 新增
        )

    async def _track_failure(
        self, session, *, error, model, task_id, attempt, user_id, datasource_id,
        duration, key_source: str = "server",
    ) -> None:
        ...
        await CostTracker(session).record_failure(
            ...,
            key_source=key_source,          # ← 新增
        )
```

`invoke` 内两处调用点补 `key_source=key_source`。

### 4.6 无效 Key 的异步口径（必须与测试/验收一致）

| 时点 | 现象 | 依据 |
|---|---|---|
| 首次使用已失效的 Key | 任务 `failed`，`error_message` 为"API Key 无效或已失效…"，凭据 `status='invalid'` | worker 内 401 → `mark_invalid` → 抛 `LLMCredentialInvalidError` |
| 之后再次触发 AI 操作 | HTTP 400 `LLM_CREDENTIAL_INVALID`（被守门拦截，不入队） | `require_llm_credential` 判定 `status != 'active'` |
| 全程 | **绝不回退服务端 Key** | `elif not ALLOW_SERVER_KEY_FALLBACK: raise` |

> 若产品要求"首次就同步 400"，只能在触发端点前置做一次真实 verify（多一次 LLM 调用/限流计数），本期不做。

> worker 解析到 `status='invalid'` 时同样抛 `LLMCredentialInvalidError`（任务 failed），**不会因为 `ALLOW_SERVER_KEY_FALLBACK=true` 而改用服务端 Key**——避免"用户 Key 失效却悄悄花部署者的钱"。

### 4.7 M2 门禁

```bash
cd backend
pytest tests/integration/test_byok_agent_injection.py -v
pytest -m "not prompt" -q          # 默认 480 用例不回归
mypy app
```

关键断言：

- 无 Key + fallback 关 → 触发端点返回 **428**，`llm_calls` 无新增行，LLM 调用 **0 次**
- 有 Key → MockTransport 捕获 `Authorization: Bearer <用户Key>`（≠ 服务端 Key）
- fallback 双态（开 → 服务端 Key；关 → 428）
- 结构化输出 repair 重试仍用用户 Key
- 用户 Key 成本累积后 `X-Cost-Status` 仍为 `NORMAL`；服务端 Key 仍可触发降级

---

## 5. M3：前端 Modal + 引导 + 演示账号

### 5.1 路径常量

`frontend/src/api/endpoints.js`：

```js
  users: {
    me: '/users/me',
    password: '/users/me/password',
    llmCredential: '/users/me/llm-credential',
    llmCredentialVerify: '/users/me/llm-credential/verify',
  },
```

### 5.2 API 封装

`frontend/src/api/llmCredential.js`（全新）：

```js
import { apiClient } from './client'
import { endpoints } from './endpoints'

/** 查询凭据状态（GET）。 */
export async function getCredentialStatus() {
  const { data } = await apiClient.get(endpoints.users.llmCredential)
  return data
}

/** 验证并保存（PUT，服务端强制连通性校验）。 */
export async function saveCredential(apiKey) {
  const { data } = await apiClient.put(endpoints.users.llmCredential, {
    api_key: apiKey,
    base_url: null,
    model: null,
  })
  return data
}

/** 删除凭据（DELETE，204）。 */
export async function deleteCredential() {
  await apiClient.delete(endpoints.users.llmCredential)
}
```

> 后端保留第 4 个端点 `POST /users/me/llm-credential/verify`（对齐已冻结需求 FR-BK-03/§7，供后续"重新验证已存 Key"使用），但**本期前端不调用**："验证并保存"是唯一入口（D4）。因此前端 3 个函数，`endpoints.users.llmCredentialVerify` 常量保留备用。

### 5.3 Hooks

`frontend/src/hooks/useLlmCredential.js`（全新）：

```js
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import * as llmCredentialApi from '../api/llmCredential'
import { notify } from '../lib/toast'

export const credentialKeys = {
  all: ['llm-credential'],
  status: () => ['llm-credential', 'status'],
}

/** 凭据状态（AI 触发引导与设置弹窗共用）。 */
export function useCredentialStatusQuery({ enabled = true, ...options } = {}) {
  return useQuery({
    queryKey: credentialKeys.status(),
    queryFn: llmCredentialApi.getCredentialStatus,
    enabled,
    staleTime: 30_000,
    ...options,
  })
}

/** 验证并保存：成功/失败由调用方（弹窗）就地展示，不额外弹 toast。 */
export function useSaveCredential() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: llmCredentialApi.saveCredential,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: credentialKeys.all })
    },
  })
}

/** 删除：成功后刷新状态。 */
export function useDeleteCredential() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: llmCredentialApi.deleteCredential,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: credentialKeys.all })
      notify.success('API Key 已删除')
    },
  })
}
```

### 5.4 演示账号常量

`frontend/src/lib/demoAccount.js`（全新）：

```js
/** 演示账号（登录页提示与弹窗文案共用；不在组件里散落字符串）。 */
export const DEMO_ACCOUNT = {
  email: 'demo@example.com',
  password: 'demo123',
}

// 注意：文案里不要出现“注册”二字——前端无注册页（router 只有 /login），
// 招聘者按提示也注册不了；demo 账号直接展示在登录框即可。
export const DEMO_MODAL_NOTICE =
  '演示账号仅供浏览；运行 AI 任务需要配置自己的 DeepSeek Key（演示账号不预置 Key）。'

export function isDemoUser(user) {
  return user?.email === DEMO_ACCOUNT.email
}
```

### 5.5 设置弹窗

`frontend/src/components/APIKeyModal/APIKeyModal.jsx`（全新，复用 `Modal` / `Input` / `Button`）：

```jsx
import { useState } from 'react'
import { Modal } from '../Modal'
import { Input } from '../Input'
import { Button } from '../Button'
import { useCredentialStatusQuery, useDeleteCredential, useSaveCredential } from '../../hooks/useLlmCredential'
import { getErrorMessage } from '../../lib/errorMessages'
import { DEMO_MODAL_NOTICE } from '../../lib/demoAccount'

export function APIKeyModal({ open, onClose, isDemo = false }) {
  const [apiKey, setApiKey] = useState('')
  const [showKey, setShowKey] = useState(false)
  const { data: status } = useCredentialStatusQuery({ enabled: open })
  const saveMutation = useSaveCredential()
  const deleteMutation = useDeleteCredential()

  const close = () => {
    setApiKey('')          // 关闭即清空，不写入任何 storage
    setShowKey(false)
    saveMutation.reset()
    onClose()
  }

  const handleSave = async () => {
    try {
      await saveMutation.mutateAsync(apiKey)
      setApiKey('')
    } catch {
      // 错误就地展示，保留输入便于修正
    }
  }

  const handleDelete = async () => {
    try {
      await deleteMutation.mutateAsync()
    } catch {
      // notify 已在 hook 内处理；保留弹窗
    }
  }

  const error = saveMutation.error ?? deleteMutation.error

  const footer = (
    <>
      {status?.configured ? (
        <Button variant="danger" size="sm" loading={deleteMutation.isPending} onClick={handleDelete}>
          删除
        </Button>
      ) : null}
      <Button variant="ghost" size="sm" onClick={close}>
        取消
      </Button>
      <Button
        size="sm"
        loading={saveMutation.isPending}
        disabled={apiKey.trim().length < 12}
        onClick={handleSave}
      >
        验证并保存
      </Button>
    </>
  )

  return (
    <Modal open={open} onClose={close} title="模型 API Key 设置" size="sm" footer={footer}>
      <p className="mb-3 text-sm text-gray-600">
        Key 仅加密保存在本系统，用于调用 DeepSeek，不会明文回显。
        <a
          className="ml-1 text-primary-600 hover:underline"
          href="https://platform.deepseek.com/api_keys"
          target="_blank"
          rel="noreferrer"
        >
          获取 Key →
        </a>
      </p>

      {isDemo ? (
        <p className="mb-3 rounded bg-amber-50 px-3 py-2 text-xs text-amber-700">
          {DEMO_MODAL_NOTICE}
        </p>
      ) : null}

      {status?.configured ? (
        <div className="mb-3 flex flex-wrap items-center gap-2 rounded bg-gray-50 px-3 py-2 text-sm">
          <span className="font-mono text-gray-900">{status.key_hint}</span>
          <span
            className={
              status.status === 'active'
                ? 'rounded bg-green-100 px-2 py-0.5 text-xs text-green-700'
                : 'rounded bg-red-100 px-2 py-0.5 text-xs text-red-700'
            }
          >
            {status.status === 'active' ? '正常' : '无效'}
          </span>
          {status.verified_at ? (
            <span className="text-xs text-gray-500">
              验证于 {new Date(status.verified_at).toLocaleString()}
            </span>
          ) : null}
        </div>
      ) : null}

      <div className="flex items-start gap-2">
        <Input
          type={showKey ? 'text' : 'password'}
          value={apiKey}
          onChange={setApiKey}
          placeholder="sk-xxxxxxxxxxxxxxxx"
          autoComplete="new-password"
          error={error ? getErrorMessage(error) : undefined}
        />
        <Button
          variant="outline"
          size="md"
          aria-label={showKey ? '隐藏 API Key' : '显示 API Key'}
          onClick={() => setShowKey(v => !v)}
        >
          {showKey ? '隐藏' : '显示'}
        </Button>
      </div>
    </Modal>
  )
}
```

> 为什么不用 `Input` 的 `suffix`：该插槽被包在 `<span aria-hidden="true">` 里（`frontend/src/components/Input/Input.jsx`），把可聚焦的按钮放进去会让读屏用户无法操作。显示/隐藏按钮因此放在 Input 外侧。

`frontend/src/components/APIKeyModal/index.js`：

```js
export { APIKeyModal } from './APIKeyModal'
```

> 安全要求：Key 只存在于组件 state，关闭/保存成功即清空；不写 `localStorage` / `sessionStorage`；不打印到控制台；`autoComplete="new-password"` 避免密码管理器回填。

### 5.6 用户菜单入口

`frontend/src/components/layout/UserMenu.jsx`：在「退出登录」之前插入菜单项，并挂载弹窗：

```jsx
import { LuKey } from 'react-icons/lu'
import { useCredentialStatusQuery } from '../../hooks/useLlmCredential'
import { useCredentialGate } from '../../lib/credentialGate'

// 组件内（弹窗由 AppLayout 的全局 Host 渲染，见 §5.7，不在菜单里再实例化）：
const { data: credentialStatus } = useCredentialStatusQuery()
const openModal = useCredentialGate(state => state.openModal)
// 后端关闭 BYOK 时隐藏入口（GET 返回 byok_enabled:false）
const showKeyEntry = credentialStatus?.byok_enabled !== false

// DropdownMenu.Content 内，退出登录之前：
{showKeyEntry ? (
  <DropdownMenu.Item
    onSelect={openModal}
    className="flex cursor-pointer items-center gap-2 rounded px-3 py-2 text-sm text-gray-700 outline-none focus:bg-gray-100"
  >
    <LuKey className="h-4 w-4" aria-hidden="true" />
    API Key 管理
  </DropdownMenu.Item>
) : null}
```

> `useCredentialStatusQuery` 在未登录/接口异常时 `data` 为 undefined，`showKeyEntry` 退化为 `true`（默认显示，功能由后端守门兜底）；只有后端明确返回"关闭"时才隐藏。

### 5.7 全局 428 守门（替代逐页 guard）

**设计**：不逐页改 5 个触发按钮，而是"点击 → 后端 428 → 全局拦截器打开弹窗"。满足 D1（按钮可点、点击后弹 Modal），改动面从 5 个页面缩到 3 个文件。

| 文件 | 作用 |
|---|---|
| `frontend/src/lib/credentialGate.js`（全新） | zustand 弹窗状态 + 供 axios 拦截器调用的非 React 入口 |
| `frontend/src/api/client.js`（改造） | 拦截器识别 428 `LLM_CREDENTIAL_NOT_CONFIGURED` → 打开弹窗 |
| `frontend/src/components/APIKeyModal/APIKeyModalHost.jsx`（全新） | 全局唯一宿主，读状态渲染 `<APIKeyModal>` |
| `frontend/src/components/layout/AppLayout.jsx`（改造） | 挂 `<APIKeyModalHost />` |

```js
// src/lib/credentialGate.js（全新）
import { create } from 'zustand'

export const useCredentialGate = create(set => ({
  open: false,
  openModal: () => set({ open: true }),
  closeModal: () => set({ open: false }),
}))

/** 供 axios 拦截器（非 React 环境）调用。 */
export function openCredentialModal() {
  useCredentialGate.setState({ open: true })
}
```

```js
// src/api/client.js（改造：在现有 response 错误拦截器里，normalizeError 之后、reject 之前）
import { openCredentialModal } from '../lib/credentialGate'

const normalized = normalizeError(error)
if (normalized.code === 'LLM_CREDENTIAL_NOT_CONFIGURED') {
  openCredentialModal()   // 不改变 reject：调用方仍可展示任务级错误
}
return Promise.reject(normalized)
```

```jsx
// src/components/APIKeyModal/APIKeyModalHost.jsx（全新）
import { APIKeyModal } from './APIKeyModal'
import { useCredentialGate } from '../../lib/credentialGate'
import { useAuth } from '../../hooks/useAuth'
import { isDemoUser } from '../../lib/demoAccount'

export function APIKeyModalHost() {
  const { open, closeModal } = useCredentialGate()
  const { user } = useAuth()
  return <APIKeyModal open={open} onClose={closeModal} isDemo={isDemoUser(user)} />
}
```

```jsx
// AppLayout.jsx（改造）：在布局根节点内挂一次
<APIKeyModalHost />
```

**口径与边界**：

- 前端真实入口 **5 个**（上传/清洗/评估/提取/报告）；**HTTP 守门点 6 个**（多一个 insights 端点，无前端入口但可直调，必须由后端拦住）；
- 不再维护 `useAiTriggerGuard` 逐页 guard（原方案要改 5 个页面 + 5 份测试）；
- 428 只来自 AI 触发端点；凭据 CRUD 返回 400/404，不触发该弹窗；
- 若 Phase 2 要求"点击零延迟弹窗"，再加页面级预检即可（后端守门仍是唯一安全边界）。

### 5.8 登录页演示账号

**口径（2026-10-28 收敛拍板）**：不建注册页、文案不提"注册"；登录框直接展示演示账号并提供"点击预填"。

`frontend/src/pages/Login/index.jsx`（现有实现用单一 `form` 对象）：

```jsx
import { DEMO_ACCOUNT } from '../../lib/demoAccount'

// prefillDemo：
const prefillDemo = () => {
  setForm({ email: DEMO_ACCOUNT.email, password: DEMO_ACCOUNT.password })
  setErrors({})
  // 不自动提交，让用户自己点登录
}

// 表单底部（现有说明文字之前）：
<div className="mt-4 flex items-center justify-between rounded bg-gray-50 px-3 py-2 text-xs text-gray-600">
  <span>
    体验账号：{DEMO_ACCOUNT.email} / {DEMO_ACCOUNT.password}
  </span>
  <button type="button" className="text-primary-600 hover:underline" onClick={prefillDemo}>
    点击预填
  </button>
</div>
```

> 说明文字（`Login/index.jsx:130`）里的"账号由管理员创建，MVP 不提供注册与找回密码"**保留不动**；演示账号提示条放在它之上，首屏可见。页面测试覆盖：点击预填后两个输入框分别出现值、且未触发登录请求。

### 5.9 错误码文案

`frontend/src/lib/errorMessages.js` 的 `MESSAGES` 追加：

```js
  LLM_CREDENTIAL_NOT_CONFIGURED: '请先配置自己的 API Key 后再使用 AI 功能',
  LLM_CREDENTIAL_INVALID: 'API Key 无效或已失效，请更新',
  LLM_CREDENTIAL_DECRYPT_FAILED: '凭据解密失败，请联系管理员重新配置',
```

同时新增 `frontend/src/lib/errorMessages.test.js` 覆盖 3 条新码（现有文件没有测试，属新增保障）。

### 5.10 M3 门禁

```bash
cd frontend
npm run lint
npm run format:check
npm run test:coverage     # lines/functions/statements ≥80、branches ≥70
npm run build
```

测试覆盖（新增源文件都要有对应用例，否则覆盖率门槛会跌破）：

| 文件 | 用例要点 |
|---|---|
| `components/APIKeyModal/APIKeyModal.test.jsx` | 未配置/已配置/无效三态渲染、显示隐藏切换、保存成功后清空+刷新、删除调用、400 错误文案 |
| `components/APIKeyModal/APIKeyModalHost.test.jsx` | 读 gate 状态渲染、close 后关闭、demo 用户带 `isDemo` |
| `hooks/useLlmCredential.test.jsx` | 状态查询 enabled 行为、保存/删除成功后 invalidate `credentialKeys.all` |
| `lib/credentialGate.test.js` | `openModal`/`closeModal` 状态迁移、`openCredentialModal()` 非 React 入口可用 |
| `api/llmCredential.test.js` | 3 个函数命中正确 path/method（verify 端点前端不调） |
| `lib/errorMessages.test.js` | 3 条新码文案 |
| `lib/demoAccount.test.js` | `isDemoUser` 判定 |
| `pages/Login/index.test.jsx`（已有则补） | 点击预填填入两个值、不自动提交 |

---

## 6. M4：演示数据 + 安全测试 + 文档同步

### 6.1 迁移 011：demo 账号（只建账号）

```bash
cd backend
alembic revision -m "011 seed demo account"
```

```python
"""011 seed demo account

只创建演示账号（不写业务数据——业务数据由 scripts/seed_demo.py 负责，
可重复执行并支持 --reset，避免迁移一次性写入后无法恢复）。

Revision ID: <生成值>
Revises: <010 的 revision>
"""
import os

import sqlalchemy as sa
from alembic import op
from passlib.context import CryptContext

revision: str = "<生成值>"
down_revision: str | None = "<010 的 revision>"
branch_labels = None
depends_on = None

DEMO_USER_ID = "00000000-0000-0000-0000-000000000001"
DEMO_EMAIL = "demo@example.com"
DEFAULT_DEMO_PASSWORD = "demo123"

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def upgrade() -> None:
    password = os.getenv("SEED_DEMO_PASSWORD", DEFAULT_DEMO_PASSWORD)
    password_hash = _pwd_context.hash(password)
    op.get_bind().execute(
        sa.text(
            """
            INSERT INTO users (id, email, password_hash, name, role, is_active, is_verified)
            VALUES (:id, :email, :password_hash, :name, 'user', true, true)
            ON CONFLICT (email) DO UPDATE
              SET password_hash = EXCLUDED.password_hash,
                  name = EXCLUDED.name,
                  is_active = true,
                  is_verified = true,
                  deleted_at = NULL,     -- 被软删的 demo 账号也能恢复登录
                  updated_at = NOW()
            """
        ),
        {
            "id": DEMO_USER_ID,
            "email": DEMO_EMAIL,
            "password_hash": password_hash,
            "name": "演示用户",
        },
    )


def downgrade() -> None:
    # demo 数据的物理删除由 scripts/seed_demo.py --reset 负责；此处仅删账号（会级联删除其数据源）
    op.get_bind().execute(
        sa.text("DELETE FROM users WHERE email = :email"),
        {"email": DEMO_EMAIL},
    )
```

> - 用 passlib `CryptContext`（与 `app/core/security.py` 一致），不要直接 `bcrypt.hashpw`；
> - `ON CONFLICT DO UPDATE` 让迁移重放时恢复固定密码（访客改不了密码）；
> - 生产用 `SEED_DEMO_PASSWORD` 注入，避免仓库里的弱口令直接暴露；
> - **环境变量注入注意**：`pydantic-settings` 只把 `.env` 读进 `settings`，**不会导出到 `os.environ`**；迁移里用 `os.getenv` 时，本地需 `export SEED_DEMO_PASSWORD=...` 后再跑 `alembic upgrade head`，容器内由 compose 环境注入。

### 6.2 demo 业务数据脚本

`backend/scripts/seed_demo.py`（全新，幂等 + `--reset`）：

```python
"""演示数据种子（data_sources → raw_data → cleaned_data）。

用法（在 backend/ 目录、激活 venv）：
    python scripts/seed_demo.py            # 幂等补齐（已存在则跳过）
    python scripts/seed_demo.py --reset    # 先删除 demo 数据源再重建
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 允许 `python scripts/seed_demo.py` 直接运行（与 prod_env_check.py 一致）
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.database import SessionLocal, dispose_engine  # noqa: E402
from app.models import (  # noqa: E402
    AnalysisResult,
    CleanedData,
    DataSource,
    KnowledgeBase,
    RawData,
    Report,
    User,
)

DEMO_EMAIL = "demo@example.com"
DEMO_DATASOURCE_ID = uuid.UUID("00000000-0000-0000-0000-000000000010")


def _now_naive() -> datetime:
    """项目 DateTime 列无时区；写库前统一转 naive（asyncpg 不接受 aware datetime）。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)

DEMO_DIALOGUES = [
    ("订单什么时候发货？", "您好，订单一般在付款后 48 小时内发出，节假日顺延 1-2 天。", 88.0),
    ("我要退款", "您好，退款申请会在 3-5 个工作日内处理，请稍等。", 72.0),
    ("产品有质量保证吗？", "我们所有产品均提供一年质保，请放心购买。", 91.0),
]


async def _ensure_datasource(session) -> DataSource:
    user = await session.scalar(select(User).where(User.email == DEMO_EMAIL))
    if user is None:
        raise SystemExit("demo 账号不存在：请先执行 alembic upgrade head")

    datasource = await session.get(DataSource, DEMO_DATASOURCE_ID)
    if datasource is not None:
        return datasource

    datasource = DataSource(
        id=DEMO_DATASOURCE_ID,
        user_id=user.id,
        name="电商客服示例数据集（2026年Q3）",
        description="预置的 AI 客服对话样例，含清洗结果与质量评分，供体验展示",
        type="customer_service",
        status="active",
        workflow_status="ready",
    )
    session.add(datasource)
    await session.flush()
    return datasource


async def _seed_rows(session, datasource: DataSource) -> None:
    base_time = _now_naive() - timedelta(days=1)
    for index, (user_message, ai_response, score) in enumerate(DEMO_DIALOGUES, start=1):
        raw_id = uuid.uuid5(DEMO_DATASOURCE_ID, f"raw-{index}")
        raw = await session.get(RawData, raw_id)
        if raw is None:
            raw = RawData(
                id=raw_id,
                datasource_id=datasource.id,
                raw_content={"format": "txt", "content": f"{user_message}\n{ai_response}"},
                status="completed",
                processed_at=base_time,
            )
            session.add(raw)
            await session.flush()

        dialogue_id = uuid.uuid5(DEMO_DATASOURCE_ID, f"dialogue-{index}")
        exists = await session.scalar(
            select(CleanedData.id).where(CleanedData.dialogue_id == dialogue_id)
        )
        if exists is not None:
            continue
        session.add(
            CleanedData(
                datasource_id=datasource.id,
                raw_data_id=raw.id,
                dialogue_id=dialogue_id,
                timestamp=base_time + timedelta(minutes=index),
                user_message=user_message,
                ai_response=ai_response,
                metadata_={"agent": "cleaning_agent", "demo": True},
                quality_score=score,
                issues=[],
            )
        )


async def _seed_analysis(session, datasource: DataSource) -> None:
    """质量评估：1 条（总分 + 5 维），固定 uuid5、不调 LLM。"""
    analysis_id = uuid.uuid5(DEMO_DATASOURCE_ID, "analysis-quality-1")
    if await session.get(AnalysisResult, analysis_id) is not None:
        return
    cleaned = await session.scalar(
        select(CleanedData).where(
            CleanedData.dialogue_id == uuid.uuid5(DEMO_DATASOURCE_ID, "dialogue-1")
        )
    )
    session.add(
        AnalysisResult(
            id=analysis_id,
            datasource_id=datasource.id,
            data_id=cleaned.id if cleaned else uuid.uuid5(DEMO_DATASOURCE_ID, "dialogue-1"),
            analysis_type="quality",
            result={
                "overall_score": 83.7,
                "dimensions": {
                    "accuracy": 86,
                    "completeness": 80,
                    "politeness": 90,
                    "efficiency": 78,
                    "compliance": 85,
                },
                "summary": "服务应答整体规范，退款时效表述可更具体。",
                "issues": ["退款处理时效未给出明确工作日上限"],
            },
            agent_name="evaluation_agent",
            agent_version="v1.0.0",
            ai_model="deepseek-flash",
            confidence=0.86,
            processing_duration=1.2,
        )
    )


async def _seed_faqs(session, datasource: DataSource) -> None:
    """知识库：3 条 FAQ + 1 条盲区（needs_review）。"""
    faqs = [
        ("订单什么时候发货？", "付款后 48 小时内发出，节假日顺延 1-2 天。", "物流"),
        ("退款多久到账？", "审核通过后 3-5 个工作日原路退回。", "售后"),
        ("产品有质保吗？", "所有产品提供一年质保。", "售后"),
    ]
    for index, (question, answer, category) in enumerate(faqs, start=1):
        faq_id = uuid.uuid5(DEMO_DATASOURCE_ID, f"faq-{index}")
        if await session.get(KnowledgeBase, faq_id) is not None:
            continue
        session.add(
            KnowledgeBase(
                id=faq_id,
                datasource_id=datasource.id,
                question=question,
                answer=answer,
                category=category,
                frequency=index,
                quality_score=88.0,
                confidence=0.9,
                source="extracted",
                is_seed=True,
            )
        )

    gap_id = uuid.uuid5(DEMO_DATASOURCE_ID, "faq-gap-1")
    if await session.get(KnowledgeBase, gap_id) is None:
        session.add(
            KnowledgeBase(
                id=gap_id,
                datasource_id=datasource.id,
                question="可以开专票吗？",
                answer="（待补充）",
                category="发票",
                frequency=12,
                quality_score=40.0,
                confidence=0.2,
                source="manual",
                status="needs_review",
            )
        )


async def _seed_report(session, datasource: DataSource) -> None:
    """报告：1 份 markdown 综合报告（不预生成 PDF/Excel，页面可现场导出）。"""
    report_id = uuid.uuid5(DEMO_DATASOURCE_ID, "report-comprehensive-1")
    if await session.get(Report, report_id) is not None:
        return
    user = await session.scalar(select(User).where(User.email == DEMO_EMAIL))
    if user is None:
        raise SystemExit("demo 账号不存在：请先执行 alembic upgrade head")
    session.add(
        Report(
            id=report_id,
            datasource_id=datasource.id,
            user_id=user.id,
            title="电商客服质量综合报告（示例）",
            report_type="comprehensive",
            format="markdown",
            status="completed",
            data={
                "summary": "整体质量 83.7 分；退款时效与专票问答为主要短板。",
                "sections": [
                    {"title": "质量概览", "content": "平均 83.7 分，好评率 67%。"},
                    {"title": "主要问题", "content": "退款时效表述模糊；发票类问题缺少标准答案。"},
                    {"title": "建议", "content": "补充退款时效 FAQ；将专票问题纳入知识库。"},
                ],
            },
            config={},
            generation_duration=2.4,
            completed_at=_now_naive(),
        )
    )


async def seed(reset: bool) -> None:
    async with SessionLocal() as session:
        if reset:
            existing = await session.get(DataSource, DEMO_DATASOURCE_ID)
            if existing is not None:
                await session.delete(existing)   # raw_data / cleaned_data 由外键级联删除
            await session.commit()

        datasource = await _ensure_datasource(session)
        await _seed_rows(session, datasource)
        await _seed_analysis(session, datasource)   # 质量评估页
        await _seed_faqs(session, datasource)       # 知识库页（含 1 条盲区）
        await _seed_report(session, datasource)     # 报告页

        statistics = dict(datasource.statistics or {})
        statistics.update(
            {
                "total_records": len(DEMO_DIALOGUES),
                "cleaned_records": len(DEMO_DIALOGUES),
                "quality_score_avg": round(
                    sum(score for _, _, score in DEMO_DIALOGUES) / len(DEMO_DIALOGUES), 2
                ),
                "last_processed_at": _now_naive().isoformat(),
            }
        )
        datasource.statistics = statistics
        await session.commit()
    await dispose_engine()
    print("demo data seeded (reset=%s)" % reset)


def main() -> None:
    parser = argparse.ArgumentParser(description="seed demo data for BYOK showcase")
    parser.add_argument("--reset", action="store_true", help="先清空 demo 数据源再重建")
    args = parser.parse_args()
    asyncio.run(seed(reset=args.reset))


if __name__ == "__main__":
    main()
```

> - 固定 UUID（`uuid5`）保证可重复执行不产生重复行；`--reset` 用于每次部署/演示前恢复被访客篡改的数据；
> - **种子覆盖 5 页**：数据源/清洗（`_seed_rows`）、质量评估（`_seed_analysis`）、知识库（`_seed_faqs`，含 1 条 `needs_review` 盲区）、报告（`_seed_report`）、Dashboard 统计（由上述数据自然产生）；
> - **部署接线**：在 `backend/scripts/docker-entrypoint.sh` 的 `alembic upgrade head` 之后追加一行，失败不阻塞启动：
>
> ```sh
> python scripts/seed_demo.py || echo "[entrypoint] seed demo data skipped"
> ```
>
> - demo 账号**不预置真实 Key**（需求 §13）——AI 按钮点击 → 后端 428 → 全局弹窗，展示 BYOK 设计本身；**"跑通 AI"不是 demo 验收口径**（见 §9 注）。

### 6.3 安全测试

`backend/tests/security/test_byok_security.py`（全新；沿用 `tests/security/conftest.py` 的异步 `client` / `db_session` / `auth_headers`）：

```python
"""BYOK 安全测试（AC-BK-04/05/11/14；AC-03 的响应脱敏在 test_llm_credential_api.py）。"""
from __future__ import annotations

import re

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select, text

from app.core.config import settings
from app.main import app
from app.models.security import AuditLog
from app.services.credential_service import credential_service

pytestmark = pytest.mark.security

KEY = "sk-userkey0000000000"
PLAINTEXT_PATTERN = re.compile(r"sk-[A-Za-z0-9]{10,}")


@pytest.fixture(autouse=True)
def byok_env(monkeypatch):
    monkeypatch.setattr(settings, "BYOK_ENABLED", True)
    monkeypatch.setattr(settings, "ALLOW_SERVER_KEY_FALLBACK", False)
    monkeypatch.setattr(settings, "CREDENTIAL_ENCRYPTION_KEY", Fernet.generate_key().decode())


@pytest.fixture(autouse=True)
def no_real_verify(monkeypatch):
    async def _ok(_api_key: str) -> bool:
        return True

    monkeypatch.setattr(credential_service, "verify", _ok)


async def test_response_has_no_plaintext_key(client, auth_headers):
    response = await client.put(
        "/api/v1/users/me/llm-credential", json={"api_key": KEY}, headers=auth_headers
    )
    assert response.status_code == 200, response.text

    payload = await client.get("/api/v1/users/me/llm-credential", headers=auth_headers)
    assert not PLAINTEXT_PATTERN.search(payload.text)
    assert payload.json()["key_hint"].endswith(KEY[-4:])


async def test_db_ciphertext_has_no_plaintext(client, auth_headers, db_session, test_user):
    await client.put(
        "/api/v1/users/me/llm-credential", json={"api_key": KEY}, headers=auth_headers
    )
    row = (
        await db_session.execute(
            text("SELECT encrypted_api_key FROM user_llm_credentials WHERE user_id = :uid"),
            {"uid": str(test_user.id)},
        )
    ).scalar_one()
    assert KEY not in row            # 密文不含明文（比断言 "sk-" 更严格、无偶然命中）


async def test_no_endpoint_accepts_other_user_id():
    """AC-BK-05：凭据端点固定操作 /me，结构上无法指定他人 user_id。"""
    paths = [route.path for route in app.routes if "llm-credential" in getattr(route, "path", "")]
    assert paths, "凭据路由未注册"
    assert all("{user_id}" not in path and "{" not in path for path in paths)


async def test_get_returns_only_own_hint(client, auth_headers):
    """AC-03/05：GET 只返回本人掩码，不泄露他人信息。"""
    await client.put(
        "/api/v1/users/me/llm-credential", json={"api_key": KEY}, headers=auth_headers
    )
    response = await client.get("/api/v1/users/me/llm-credential", headers=auth_headers)
    body = response.json()
    assert body["configured"] is True
    assert body["key_hint"] == f"{KEY[:5]}…{KEY[-4:]}"
    assert KEY not in response.text


async def test_audit_log_has_no_secret(client, auth_headers, db_session, test_user):
    await client.put(
        "/api/v1/users/me/llm-credential", json={"api_key": KEY}, headers=auth_headers
    )
    rows = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.user_id == test_user.id)
        )
    ).scalars().all()
    assert any(row.action == "credential_configured" for row in rows)
    for row in rows:
        assert not PLAINTEXT_PATTERN.search(str(row.details or {}))


async def test_base_url_rejected_without_http_call(client, auth_headers, monkeypatch):
    calls: list[str] = []

    async def _verify(api_key: str) -> bool:
        calls.append(api_key)
        return True

    monkeypatch.setattr(credential_service, "verify", _verify)
    response = await client.put(
        "/api/v1/users/me/llm-credential",
        json={"api_key": KEY, "base_url": "http://internal.evil.com"},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "LLM_CREDENTIAL_INVALID"
    assert calls == []   # 未发起任何校验/外呼
```

> `test_no_endpoint_accepts_other_user_id` 的写法可按实现微调：核心是断言"没有任何凭据端点接受 user_id 路径/查询参数"。

### 6.4 E2E（Playwright）——本期延后

> **收敛拍板（2026-10-28）**：BYOK E2E 本期不做。理由：弹窗三态已由 `APIKeyModal.test.jsx` 覆盖，428/400 由集成测试覆盖；`frontend/e2e` 现有 **8 条**真栈用例继续作为回归门禁（AC-BK-12 仍为 8 条，不新增）。下面是 Phase 2 参考稿，本期不落文件。

`frontend/e2e/byok.spec.js`（Phase 2 参考，本期不实现）。**用路由拦截保证确定性**，不依赖真实 DeepSeek 网络：

```js
import { expect, test } from '@playwright/test'
import { loginViaUi } from './fixtures'

const ENDPOINT = '**/api/v1/users/me/llm-credential'

test.describe('BYOK 凭据设置', () => {
  test('用户菜单打开弹窗；无 Key 时状态为未配置', async ({ page }) => {
    await page.route(ENDPOINT, route =>
      route.request().method() === 'GET'
        ? route.fulfill({ status: 200, json: { byok_enabled: true, configured: false } })
        : route.continue()
    )
    await loginViaUi(page)
    await page.getByRole('button', { name: '打开用户菜单' }).click()
    await page.getByRole('menuitem', { name: 'API Key 管理' }).click()

    await expect(page.getByRole('dialog')).toBeVisible()
    await expect(page.getByText('模型 API Key 设置')).toBeVisible()
  })

  test('保存成功 → 状态变为已配置并显示掩码', async ({ page }) => {
    let configured = false   // 有状态 mock：PUT 成功后 GET 返回已配置
    await page.route(ENDPOINT, route => {
      if (route.request().method() === 'PUT') {
        configured = true
        return route.fulfill({
          status: 200,
          json: {
            byok_enabled: true,
            configured: true,
            provider: 'deepseek',
            key_hint: 'sk-x…a1b2',
            status: 'active',
            verified_at: new Date().toISOString(),
          },
        })
      }
      return route.fulfill({
        status: 200,
        json: configured
          ? {
              byok_enabled: true,
              configured: true,
              provider: 'deepseek',
              key_hint: 'sk-x…a1b2',
              status: 'active',
              verified_at: new Date().toISOString(),
            }
          : { byok_enabled: true, configured: false },
      })
    })
    await loginViaUi(page)
    await page.getByRole('button', { name: '打开用户菜单' }).click()
    await page.getByRole('menuitem', { name: 'API Key 管理' }).click()
    await page.getByPlaceholder('sk-xxxxxxxxxxxxxxxx').fill('sk-validkeyformat00')
    await page.getByRole('button', { name: '验证并保存' }).click()

    await expect(page.getByText('sk-x…a1b2')).toBeVisible()
  })

  test('校验失败 → 展示错误文案且输入保留', async ({ page }) => {
    await page.route(ENDPOINT, route => {
      if (route.request().method() === 'PUT') {
        return route.fulfill({
          status: 400,
          json: {
            error: {
              code: 'LLM_CREDENTIAL_INVALID',
              message: 'API Key 连通性校验失败',
            },
          },
        })
      }
      return route.fulfill({ status: 200, json: { byok_enabled: true, configured: false } })
    })
    await loginViaUi(page)
    await page.getByRole('button', { name: '打开用户菜单' }).click()
    await page.getByRole('menuitem', { name: 'API Key 管理' }).click()
    await page.getByPlaceholder('sk-xxxxxxxxxxxxxxxx').fill('sk-invalidkey0000')
    await page.getByRole('button', { name: '验证并保存' }).click()

    await expect(page.getByText('API Key 无效或已失效，请更新')).toBeVisible()
  })
})
```

> 如需真实后端联调，另加 `E2E_BYOK_REAL=1` 的用例（不拦截路由），CI 默认不跑（真实 Key 不可用）。

### 6.5 文档同步清单（与代码同 PR）

| 文档 | 章节 | 改动 |
|---|---|---|
| `docs/01-requirements/04-...BYOK.md` | §6、§13、§16、§17、§19 | **已完成 v0.4.1**：迁移 009/010/011、D6~D11、演示验收口径、工时 4.2 |
| `docs/03-architecture/04-API设计.md` | §12.1、§12.2、新「BYOK 凭据」章节 | 428；3 条错误码；4 个端点契约 |
| `docs/03-architecture/03-数据库设计.md` | 新表章节 + `llm_calls` | `user_llm_credentials` DDL、`key_source`、审计 action |
| `docs/05-design/03-页面设计规范.md` | 组件/交互 | API Key Modal、未配置引导、演示账号提示 |
| `docs/04-development/15-上线验收清单.md` | §1、§5、§6 | 端点计数 +4；安全项；已知限制（demo 数据可被篡改，靠脚本重置） |
| `backend/.env.example` | BYOK 段 | 5 项配置（含 `SEED_DEMO_PASSWORD`） |
| `backend/.env.production.example` | BYOK 段 | `ALLOW_SERVER_KEY_FALLBACK=false`、密钥注入说明 |
| `.github/workflows/test.yml` | backend job `env` | 注入 `BYOK_ENABLED` / `CREDENTIAL_ENCRYPTION_KEY` / `ALLOW_SERVER_KEY_FALLBACK=true` |
| `.github/workflows/e2e.yml` | `env` | 同上（后端服务与 E2E 都要） |
| 本文（16 号） | §11 | 记录 v2.0 修订 |

### 6.6 PR 拆分建议

| PR | 内容 | 门禁 |
|---|---|---|
| PR-1 | M0 契约 + config + errors/exceptions + 加密服务 + 模型 + 迁移 009 + **同步 `test_errors.py` / `test_models_schema.py`** | 单测 + 迁移双向 + mypy/black/flake8 |
| PR-2 | Schema + credential_service + 4 API（verify 端点保留、前端不调）+ 限流 + 集成/安全测试 | M1 门禁全绿 |
| PR-3 | HTTP 守门 + Agent 注入 + CostTracker/`_track_*` + **`tests/conftest.py` fallback 开关 + CI env** | M2 门禁 + 默认 480 用例不回归 |
| PR-4 | 前端（endpoints/api/hooks/Modal + 全局 428 Host + 菜单入口 + 登录页）+ 前端测试 | lint/format/coverage/build |
| PR-5 | 迁移 011 + `seed_demo.py`（5 页）+ entrypoint 接线 + 文档同步（E2E 延后） | 全量回归 + demo 5 页可看 |

### 6.7 M4 门禁

```bash
cd backend && pytest -m "not prompt" -q
cd frontend && npm run lint && npm run test:coverage && npm run build
cd frontend && npx playwright test
```

---

## 7. 测试策略

### 7.1 分层与标记

| 层 | 目录 | 标记 | 依赖 |
|---|---|---|---|
| 单元 | `tests/unit/` | `@pytest.mark.unit`（现有用例多数不标） | 无外部服务 |
| 集成 | `tests/integration/` | `pytestmark = pytest.mark.integration` | 真实 PG + Redis（`docker-compose.test.yml`） |
| 安全 | `tests/security/` | `pytestmark = pytest.mark.security` | 同集成 |
| E2E | `frontend/e2e/` | Playwright | 真实前后端（或路由 mock） |

项目约定：`asyncio_mode = auto`（无需 `@pytest.mark.asyncio`）；默认 `-m "not prompt"`；`--strict-markers`，新标记必须登记到 `pytest.ini`。

### 7.2 必用的 fixture 与开关

```python
# 集成/安全测试现成 fixture（不要自造 session/client）
db_session     # 事务隔离会话（用例结束回滚）
client         # ASGITransport 异步客户端，get_db 已指向 db_session
test_user      # 已持久化普通用户（TEST_USER_PASSWORD = "secret123"）
auth_headers   # 登录后的 Authorization 头
```

BYOK 用例需要 `monkeypatch` 三个开关（`conftest` 默认关闭全局 IP 限流，但**不影响**本端点的 Redis 限流）。注意：`tests/conftest.py` 会有全局 autouse fixture 把 `ALLOW_SERVER_KEY_FALLBACK` 置为 `True`（见 §3.2，保证存量 202 用例不回归），BYOK 用例必须显式改回 `False`：

```python
@pytest.fixture(autouse=True)
def byok_settings(monkeypatch):
    monkeypatch.setattr(settings, "BYOK_ENABLED", True)
    monkeypatch.setattr(settings, "ALLOW_SERVER_KEY_FALLBACK", False)
    monkeypatch.setattr(settings, "CREDENTIAL_ENCRYPTION_KEY", Fernet.generate_key().decode())
```

### 7.3 Mock 策略

| 目标 | 做法 |
|---|---|
| 跳过真实 verify（保存流程） | `from app.services.credential_service import credential_service` 后 `monkeypatch.setattr(credential_service, "verify", async_fn)`（必须拿**单例**，不能 `from app.services import credential_service`——那是子模块） |
| 断言用户 Key 注入 + 请求头 | 先保存真类再替换：`_Real = base_module.LLMClient` → `def factory(**kw): return _Real(transport=httpx.MockTransport(handler), **kw)` → `monkeypatch.setattr("app.agents.base.LLMClient", factory)`；handler 记录 `authorization` 头 |
| Agent 单元级替换 | 构造 `BaseAgent(..., llm=_FakeLLM([...]))`（仅在无用户 Key 的 fallback 路径生效；有 Key 时 invoke 会新建客户端，必须用上面的 factory） |
| verify 限流 | 使用真实 Redis（集成环境）；把 `LLM_CREDENTIAL_VERIFY_PER_MINUTE` 调小后连打 |

### 7.4 覆盖矩阵

| AC | 测试文件 | 关键断言 |
|---|---|---|
| 01 | `tests/integration/test_byok_agent_injection.py` | 触发端点 428；LLM 调用 0 次；`llm_calls` 无新增 |
| 02 | `tests/integration/test_byok_agent_injection.py` | `authorization == "Bearer <用户Key>"`，≠ 服务端 Key |
| 03 | `tests/integration/test_llm_credential_api.py` | 响应正则不命中、`key_hint` 前5后4 |
| 04 | `tests/security/test_byok_security.py` | 密文不含明文 |
| 05 | `tests/security/test_byok_security.py` | 端点不含 user_id 参数；admin 只见自己 |
| 06 | `tests/integration/test_llm_credential_api.py` | DELETE → 再触发 428；再 PUT → 可用 |
| 07 | `tests/integration/test_byok_agent_injection.py` | 401 → `invalid`（幂等）+ 二次触发 400；不回退 |
| 08 | `tests/integration/test_byok_agent_injection.py` | fallback 双态 |
| 09 | `tests/unit/test_credential_encryption.py` | 密钥缺失/非法 → 错误、无明文入库 |
| 10 | `tests/integration/test_llm_credential_api.py` | 第 6 次 verify → 429 |
| 11 | `tests/security/test_byok_security.py` | 审计行存在且无 Key |
| 12 | CI | 默认 480 / 全量 735 不新增失败；前端全量；E2E **现有 8 条**（不新增）；覆盖率门槛 |
| 13 | `tests/integration/test_byok_agent_injection.py` | 老用户无凭据登录/浏览 200 |
| 14 | `tests/security/test_byok_security.py` | `base_url` → 400 且 `verify` 未被调用 |
| 15 | `tests/integration/test_byok_agent_injection.py` | `key_source='user'` 记录；用户 Key 成本不触发降级 |

### 7.5 常用命令

```bash
cd backend
pytest                                        # 默认 480 用例
pytest tests/unit/test_credential_encryption.py tests/integration/test_llm_credential_api.py \
       tests/integration/test_byok_agent_injection.py tests/security/test_byok_security.py -v
pytest --collect-only                         # 基线核对（默认 480 / 全量 735）
black --check app tests && flake8 app tests && mypy app

cd frontend
npm run test:coverage
npx playwright test e2e/byok.spec.js
```

---

## 8. 配置参考

### 8.1 本地开发（`backend/.env`）

```ini
# ── BYOK ──────────────────────────────────────────────
BYOK_ENABLED=true
# 生成：python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
CREDENTIAL_ENCRYPTION_KEY=<your-fernet-key>
# 本地可用服务端 Key 调试；生产必须 false
ALLOW_SERVER_KEY_FALLBACK=true
LLM_CREDENTIAL_VERIFY_PER_MINUTE=5
SEED_DEMO_PASSWORD=demo123
```

### 8.2 CI / E2E

```yaml
env:
  BYOK_ENABLED: "true"
  CREDENTIAL_ENCRYPTION_KEY: ${{ secrets.CREDENTIAL_ENCRYPTION_KEY }}
  ALLOW_SERVER_KEY_FALLBACK: "true"   # CI 无真实 Key，走服务端 Key（需 DEEPSEEK_API_KEY 占位）
  DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}
  SEED_DEMO_PASSWORD: "demo123"
```

> CI 里不要调用真实 `verify`：集成测试 `monkeypatch credential_service.verify`；E2E 用路由拦截。若必须跑真实链路，放 `-m prompt` / 手动任务。

### 8.3 生产

```ini
BYOK_ENABLED=true
CREDENTIAL_ENCRYPTION_KEY=<通过 Secrets Manager 注入>
ALLOW_SERVER_KEY_FALLBACK=false   # 生产必须 false
LLM_CREDENTIAL_VERIFY_PER_MINUTE=5
SEED_DEMO_PASSWORD=<单独注入的演示密码>
```

> ⚠️ `CREDENTIAL_ENCRYPTION_KEY` 丢失 → 所有已存凭据不可恢复（Phase 1 单密钥，Phase 2 才上 MultiFernet）。必须在 Secrets Manager 备份，并在部署文档中明确交接；轮换前需通知用户重配。

---

## 9. 验收清单（AC-BK-01~15）

> 与 v1.0 的差异：AC-05 改写（`/me` 固定端点）、AC-12 去数字化、AC-07 按异步口径、AC-15 增加降级响应头断言。
>
> **业务收敛口径（2026-10-28 拍板）**：① 独立 `POST /verify` 端点保留实现、前端不调用（AC-10 仍按该端点测限流）；② 审计只要求"最小写入 `audit_logs`"，不要求查询/导出（AC-11 按此判过）；③ BYOK 不新增 E2E，回归仍以现有 8 条为准（AC-12）；④ **demo 账号不验收"跑通 AI"**——它无 Key，永远停在 428→弹窗，demo 验收口径 = 5 页有产出 + AI 按钮可点且弹窗文案正确。

| 编号 | 验收标准 | 测试文件 | 状态 |
|---|---|---|---|
| AC-BK-01 | 无 Key + fallback 关 → 触发端点 428 `LLM_CREDENTIAL_NOT_CONFIGURED`；无 LLM 请求；无 `llm_calls` 记录 | test_byok_agent_injection.py | ☐ |
| AC-BK-02 | Agent 调用 `Authorization` 为用户 Key，非服务端 Key | test_byok_agent_injection.py | ☐ |
| AC-BK-03 | GET 响应无完整 Key；仅 `key_hint`（前5…后4） | test_llm_credential_api.py | ☐ |
| AC-BK-04 | DB 密文不含明文子串 | test_byok_security.py | ☐ |
| AC-BK-05 | 凭据端点固定 `/me`，无可指定他人 user_id 的入口；admin 亦只能读写自己 | test_byok_security.py | ☐ |
| AC-BK-06 | 删除后 AI 操作恢复 428；再配置后恢复可用 | test_llm_credential_api.py | ☐ |
| AC-BK-07 | 无效 Key verify 400；worker 401 → invalid（幂等）；二次触发 HTTP 400；绝不回退服务端 Key | test_byok_agent_injection.py | ☐ |
| AC-BK-08 | fallback 双态正确（开→服务端 Key；关→428） | test_byok_agent_injection.py | ☐ |
| AC-BK-09 | `CREDENTIAL_ENCRYPTION_KEY` 缺失/非法 → 保存失败，无明文入库 | test_credential_encryption.py | ☐ |
| AC-BK-10 | verify 端点超 5 次/分钟/用户 → 429 `RATE_LIMIT_EXCEEDED`（端点保留、前端不调） | test_llm_credential_api.py | ☐ |
| AC-BK-11 | 设置/删除/失效写 `audit_logs`（最小写入即可，不要求查询/导出），日志无 Key 明文 | test_byok_security.py | ☐ |
| AC-BK-12 | 回归门禁：CI 全绿（默认 480 / 全量 735、前端全量、**E2E 现有 8 条不新增**、覆盖率 80/70）；存量 6 处 202 用例依赖测试环境 `ALLOW_SERVER_KEY_FALLBACK=true`（见 §3.2） | CI | ☐ |
| AC-BK-13 | 老用户/种子账号迁移后登录、只读浏览正常 | test_byok_agent_injection.py | ☐ |
| AC-BK-14 | Phase 1 非空 `base_url` → 400，无外部 HTTP 请求 | test_byok_security.py | ☐ |
| AC-BK-15 | 用户 Key 调用 `key_source='user'`，`X-Cost-Status` 不降级；服务端 Key 仍受约束 | test_byok_agent_injection.py | ☐ |

---

## 10. 常见问题

**Q：本地 verify 总失败，怎么跳过？**  
A：分两种场景：① 只做后端开发 → `BYOK_ENABLED=false`（整体回退服务端 Key，前端入口自动隐藏）；② 要联调 BYOK 前端 → 必须配置 `CREDENTIAL_ENCRYPTION_KEY`，并 monkeypatch/路由拦截 verify。不要用"缺密钥 + fallback"绕过（会掩盖 fail-closed 问题）。

**Q：迁移提示 revision 找不到？**  
A：迁移链是 `008(9b2d4f6a8c1e) → 009(建表) → 010(key_source) → 011(demo 账号)`；`down_revision` 必须指向链上紧邻的上一个 revision（`alembic history` 可查）。文件名必须由 `alembic revision` 生成，不要手写。

**Q：为什么 428 在 API 返回，而不是 Agent 里？**  
A：5 条链路都是 Celery 异步任务，HTTP 先返回 202；Agent 内抛异常只会变成任务 failed。守门必须在请求进入队列前（`require_llm_credential`）。详见 §2.1 / 17 号文档 S1-03。

**Q：为什么首次用了失效 Key 时看不到 400？**  
A：异步执行，首次 401 只能发生在 worker（任务 failed + 标记 invalid）；**下一次**触发才被 HTTP 守门拦成 400。见 §4.6。若产品要求首次同步提示，需要触发前额外 verify（多一次 LLM 调用，不建议）。

**Q：为什么 demo 数据不在迁移里？**  
A：迁移只跑一次，`ON CONFLICT DO NOTHING` 无法恢复被访客篡改的数据。demo 账号放迁移 **011**，业务数据放 `scripts/seed_demo.py --reset`，部署时执行。

**Q：Phase 2 开放 `base_url` 要改什么？**  
A：删除路由层 `base_url` 拒绝校验；加 URL 白名单（仅 `https://`）+ 私网地址过滤（`10/8`、`172.16/12`、`192.168/16`、`127/8`、`localhost`、IPv6 内网）；同步更新需求 FR-BK-02a 与 API 文档。

**Q：接上 BYOK 后跑全量测试，为什么存量「上传/清洗/评估/洞察/提取/报告」用例全变 428？**  
A：默认 `ALLOW_SERVER_KEY_FALLBACK=false`，而存量用例用无凭据用户断言 202。按 §3.2 在 `tests/conftest.py` 加 autouse fixture 把开关置 `True`（并给 CI 注入同名环境变量）；BYOK 的 428 用例再在用例内显式改回 `False`。

**Q：demo 账号点 AI 为什么不会真的跑？验收怎么算过？**  
A：demo 账号**不预置 Key**（需求 §13），所以点 AI 必然走 428 → 全局弹窗，这是设计本身而不是故障。验收口径：① 登录页展示演示账号并能预填登录；② **5 组产出**有预置数据（Dashboard 统计、数据源/清洗、质量评估、知识库、报告）；③ 点任意 AI 按钮 → 弹窗出现且文案正确（无"注册"字样）。**不验收"跑通 AI"**。

**Q：为什么没有注册页？是不是漏做了？**  
A：`frontend/src/router.jsx` 只有 `/login`，`Login/index.jsx:130` 明写"MVP 不提供注册与找回密码"；后端 `POST /auth/register` 存在但前端未接入。业务收敛（2026-10-28）决定本期**不建注册页**：登录框直接展示演示账号 + 点击预填，文案不提"注册"，避免指向死链。自助注册/邀请制属后续用户体系需求。
**Q：如何统计"用户自付"的成本？**  
A：`llm_calls.key_source='user'` 的行即用户 Key 调用（含估算成本）；`get_usage_stats` 不过滤来源，降级统计（`get_daily_cost`）只算 `server`。

---

## 11. 变更记录

| 版本 | 日期 | 变更摘要 |
|---|---|---|
| v1.0 | 2026-10-28 | 初稿：M1–M4 四阶段、代码骨架、AC 表 |
| v2.0 | 2026-10-28 | **按代码库全量核验修订**：① 428 改为 HTTP 守门 + worker 兜底（原方案会变成 202→failed）；② 错误码/异常类按项目白名单落地，禁用 `HTTPException(detail={})` 与 Pydantic 类校验产 422；③ 成本过滤改到 `CostTracker.get_daily_cost`，`key_source` 四层透传；④ 路由/依赖/Schema/服务路径全部对齐真实结构；⑤ 迁移 010 只建 demo 账号，业务数据移入可重置脚本；⑥ 前端改为 endpoints/api/hooks/Modal 四层；⑦ 测试 fixture、E2E 目录、CI 门禁按实际工程修正；⑧ AC-05/07/12/15 口径修订 |
| v2.1 | 2026-10-28 | 并入独立对抗性校验结果：① 同步 `test_errors.py`（28 条码/允许 428）与 `test_models_schema.py`（16 张表）；② `tests/conftest.py` 加 `ALLOW_SERVER_KEY_FALLBACK=true` autouse fixture + CI env，保住存量 480 用例与 6 处 202 断言；③ 补 `LLMAuthenticationError` import、修正 `record_agent_invocation` kwarg；④ 统一 `_now_naive()` 写库（asyncpg 拒收 aware datetime）；⑤ seed 脚本补 `sys.path` bootstrap；⑥ `mark_invalid` 按 `rowcount` 写审计；⑦ UserMenu 按 `byok_enabled` 条件渲染；⑧ 显示/隐藏按钮移出 `Input.suffix` 的 `aria-hidden` 槽位；⑨ §7.3 mock factory 先保存真类避免递归；⑩ 迁移 010 `ON CONFLICT` 复位 `deleted_at`；⑪ 前端新增 5 个源文件的测试清单；⑫ 修正 §4.4"三处"、§3.7 笔误、AC-03 归属等一致性 |
| v2.2 | 2026-10-28 | **业务收敛拍板落地**（决策稿 [BYOK-业务收敛-v1](../07-review/BYOK-业务收敛-v1.md)）：① 不建注册页、文案删"注册"，登录页直接展示 demo 账号 + 点击预填；② demo 验收口径改为"5 页有产出 + 点 AI 弹窗"，**不验收跑通 AI**；③ 5 处逐页 guard 改为**全局 428 拦截器 + 唯一 Modal Host**（改动从 5 页缩到 3 文件）；④ 独立 verify 端点**保留实现、前端不调用**（对齐冻结需求）；⑤ 审计只做最小写入、E2E 本期延后（AC-12 仍为现有 8 条）；⑥ demo 种子补到 5 页（评估/知识库/报告各 1 组，固定 uuid5，+0.3d）；⑦ 本期配 DeepSeek 单价；⑧ 工时 5.0 → **4.2 人日**（M3 1.0→0.6、M4 1.0→0.6） |
| v2.3 | 2026-10-28 | **实现对齐**：迁移实际拆为 **009 建表 / 010 `key_source` / 011 demo 账号**（§3.6、§6.1、§2.4 同步）；前端 M3 落地（全局 428 + `APIKeyModalHost` + 菜单入口 + 登录页展示/预填 + `errorMessages` 3 条）；后端 4 端点/审计/`key_source` 四层透传实现完成；`.env.example`、CI、`requirements.txt` 同步；集成测试 `test_llm_credential_api.py` 7 条通过 |


