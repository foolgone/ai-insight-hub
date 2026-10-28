# BYOK 勘误与修订实施计划

> **文档编号**：17  
> **文档版本**：v1.3（已应用）  
> **创建日期**：2026年10月28日  
> **文档状态**：已应用——16 号文档已于 2026-10-28 按本文修订为 v2.0；本文保留为勘误依据与决策记录  
> **勘误对象**：[16-BYOK开发指南](./16-BYOK开发指南.md)（v1.0，1335 行）  
> **上游依据**：[04-需求-用户自带LLM-API-Key（BYOK）](../01-requirements/04-需求-用户自带LLM-API-Key（BYOK）.md)（v0.3，已冻结）、[01-开发规范](./01-开发规范.md)、[04-API设计](../03-architecture/04-API设计.md)、[03-数据库设计](../03-architecture/03-数据库设计.md)、[15-上线验收清单](./15-上线验收清单.md)  
> **核验基线**：`main@f170192`（2026-10-28）；需求文档当前存在**未提交改动**

---

## 0. 结论与使用方式

### 0.1 一句话结论

16 号文档的**方案骨架可用**（Fernet 加密、单表凭据、4 个 API、`key_source` 成本隔离、fallback 开关、AC 划分都是对的），但它不是"复制即跑"的施工图：其中 **14 处置信代码库后必然失败（S1）**、**12 处实现位置/链路错误会导致返工（S2）**、**10 处口径与文档同步缺口（S3）**。

最危险的三处不是代码细节，而是**架构位置错误**：

| # | 16 号文档的做法 | 实际后果 |
|---|---|---|
| 1 | 在 `BaseAgent.invoke` 内 `raise 428` | `invoke` 的 `try/except Exception` 会把异常吞成 `AgentResult(success=False)`，而 5 条 AI 链路都是 **Celery 异步任务**——用户先收到 202，几秒后任务变 failed。HTTP 层永远拿不到 428 |
| 2 | 在 `degradation_middleware.py` 里改"当日成本 SQL" | 中间件里没有成本 SQL，它只调 `DegradationManager → CostTracker.get_daily_cost()`；改错文件等于没改 |
| 3 | 迁移 010 往 `cleaned_data` 插 demo 数据 | 该表**没有 `updated_at` 列**、`raw_data_id`/`timestamp` 为 NOT NULL、`dialogue_id` 是 UUID 类型——迁移直接报错，`alembic upgrade head` 卡住，后面所有环境起不来 |

### 0.2 怎么用本文

| 场景 | 用法 |
|---|---|
| 直接开工 | 按 §6 任务清单（M0→M4）逐条做，每条都有文件路径与门禁 |
| 评审 | 先看 §2、§3 的 S1/S2 明细与 §5 的设计决策 |
| 回写 16 号文档 | 已完成：16 号已升 **v2.0**（见其 §11 变更记录）；本文 §9 附录为差异索引，可对照复核 |
| 对齐架构文档 | 按 §6.9 文档同步清单，与代码同 PR 提交 |
| 验收 | 按 §7 修订版 AC 口径，替换 16 号文档 §9 的验收表 |

### 0.3 处置原则

1. **16 号文档保留为设计意图稿，不删不改骨架**；本文是其增量权威修订，冲突时以本文为准。
2. 所有"改哪里"都以**当前代码库路径**为准，不以文档理想路径为准。
3. 新增错误码、新增表、新增字段都属于"架构契约"，**必须先同步 `docs/03-architecture/` 再改代码**（项目规则：错误码严格取自 API 设计 §12.2，"不得自造"）。
4. 前端凡是新接口，必须走 `endpoints.js → api/*.js → hooks/*.js → 组件` 四层，不允许组件里直拼路径（开发规范 A-1）。

---

## 1. 核验环境与基线（可复现）

| 项 | 实测结论 | 依据 / 命令 |
|---|---|---|
| 迁移链 head | `008`，revision `9b2d4f6a8c1e`，下一个编号 `009` | `ls backend/migrations/versions/` |
| Alembic 文件命名模板 | `%(year)d%(month).2d%(day).2d_%(hour).2d%(minute).2d_%(rev)s_%(slug)s`（即 `20261027_2100_<rev>_008_<slug>.py`） | `backend/alembic.ini:6` |
| 数据库扩展 | `vector` / `pg_trgm` / `pgcrypto` 已启用（`gen_random_uuid()` 可用） | `migrations/versions/*001_*.py:23-25` |
| 后端测试基线 | 默认收集 **480** 个用例，全量 **735** 个（`-m "not prompt"` 默认排除 255 个） | `backend/venv/Scripts/python.exe -m pytest --collect-only`；`backend/pytest.ini:10` |
| 测试标记 | `unit` / `integration` / `prompt` / `slow` / `security` / `perf`；`--strict-markers` | `backend/pytest.ini:10-17` |
| 集成测试环境 | 需真实 PostgreSQL/Redis，`docker-compose.test.yml`；clients 见 `tests/integration/conftest.py`（`db_session` / `client` / `test_user`） | 同文件 |
| 后端质量门禁 | CI 阻塞：`black --check`、`flake8`、`mypy app`、`pytest --cov-fail-under=80` | `.github/workflows/test.yml` |
| 前端测试基线 | vitest；67 个测试文件；**301 个用例声明**（295 × `it(` + 6 × `it.each(`，each 展开后更多） | `grep -rho "it(\|it.each(" frontend/src --include=*.test.*` |
| 前端质量门禁 | `eslint --max-warnings 0`、`prettier --check`、覆盖率 lines/functions/statements ≥80、branches ≥70、`vite build` | `.github/workflows/test.yml`、`frontend/package.json` |
| E2E | Playwright，`frontend/e2e/` 下 6 个 spec、**8 条用例**（`frontend/e2e/*.spec.js`），CI 见 `.github/workflows/e2e.yml` | `grep -c "test("` |
| 依赖 | `cryptography` **未在 `requirements.txt` 显式声明**（仅由 `python-jose[cryptography]` 间接带入）；`bcrypt==4.0.1`、`passlib[bcrypt]==1.7.4` 已锁 | `backend/requirements.txt:44-47` |
| 错误码体系 | `ErrorCode` 25 条业务码 + `FrameworkErrorCode` 3 条；`ERROR_STATUS` 映射 HTTP；API 设计 §12.1 **没有 428** | `backend/app/core/errors.py`、`docs/03-architecture/04-API设计.md:1671-1723` |
| 审计表 | `AuditLog` 在 `app/models/security.py:68`，`resource_id` 是 **UUID 列**，`details` JSONB；全项目**无任何审计写入点** | 同文件 |
| AI 触发链路 | 5 条链路全部走 Celery：`enqueue_clean/evaluation/insight/extract/report` → `app/tasks/*.py`；失败落 `tasks.status='failed'` | `app/services/*_service.py`、`app/tasks/` |
| 需求文档状态 | `git status`：需求文档 M（未提交）；16 号指南 ??（未跟踪） | `git status --porcelain` |

> 说明：前端单测无法在本机沙箱内实跑（`vitest` 需要 spawn 子进程，被沙箱限制），上表前端数字为静态统计；**精确用例数在 CI 覆盖率报告中读取**。

---

## 2. S1 勘误：照抄即失败（14 项）

> 判定标准：代码不能导入/不能运行/违反项目硬性规范/安全要求不成立。

### S1-01 异常构造签名不存在（`error_code=` 是自造参数）

- **文档位置**：§3.2（L175-187、L202-206）、§4.1（L722-727、L746-750）
- **文档写法**：`AIInsightHubException(error_code="...", message="...", status_code=500)`
- **实际签名**：`AIInsightHubException(message=None, *, details=None, code=None, status_code=None, headers=None)`，`code` 是 `ErrorCode` 枚举；**没有 `error_code` 参数**，第一个位置参数是 message。照抄会 `TypeError`。
- **依据**：`backend/app/core/exceptions.py:22-45`
- **修订**：按项目既有模式，新增 3 个异常子类（class 级 `code`），业务代码只抛子类：

```python
# app/core/exceptions.py 追加
class LLMCredentialNotConfiguredError(AIInsightHubException):
    code = ErrorCode.LLM_CREDENTIAL_NOT_CONFIGURED
    default_message = "请先配置您的 DeepSeek API Key"


class LLMCredentialInvalidError(AIInsightHubException):
    code = ErrorCode.LLM_CREDENTIAL_INVALID
    default_message = "API Key 无效或已失效，请更新后再试"


class LLMCredentialDecryptError(AIInsightHubException):
    code = ErrorCode.LLM_CREDENTIAL_DECRYPT_FAILED
    default_message = "凭据解密失败，加密密钥可能已更换"
```

### S1-02 新增错误码绕不过"错误码白名单"

- **文档位置**：§3.2/§3.6/§4.1 全篇使用 `LLM_CREDENTIAL_*` 与自造的 `CREDENTIAL_CONFIG_ERROR`
- **问题三层**：
  1. `app/core/errors.py` 文件头明确"业务错误码严格取自 API §12.2 的 25 条，**不得自造**"；当前 `ErrorCode` 里没有这 3 个码；
  2. API 设计 §12.1 状态码表**没有 428**，§12.2 错误码表**没有** `LLM_CREDENTIAL_*`（需求文档 §7 已定义，但架构文档未回写）；
  3. 前端 `frontend/src/lib/errorMessages.js` 只映射 21 个 MVP 码 + 4 个 Phase 2 码，新码会退化为"操作失败，请稍后重试"。
  4. `CREDENTIAL_CONFIG_ERROR` 连需求文档都没有，属于文档自造，应删除（密钥缺失场景复用 `LLM_CREDENTIAL_DECRYPT_FAILED`，或直接 `INTERNAL_ERROR`）。
- **修订**（顺序不可颠倒）：先在 `docs/03-architecture/04-API设计.md` §12.1 增 `428`、§12.2 增 3 条码并标注"BYOK"，再改 `app/core/errors.py`（`ErrorCode` + `ERROR_STATUS`：428/400/500），最后补 `frontend/src/lib/errorMessages.js` 文案与前端 428/429 处理测试。

```python
# app/core/errors.py
class ErrorCode(str, Enum):
    ...
    # 428 / 400 / 500（BYOK）
    LLM_CREDENTIAL_NOT_CONFIGURED = "LLM_CREDENTIAL_NOT_CONFIGURED"
    LLM_CREDENTIAL_INVALID = "LLM_CREDENTIAL_INVALID"
    LLM_CREDENTIAL_DECRYPT_FAILED = "LLM_CREDENTIAL_DECRYPT_FAILED"

ERROR_STATUS[ErrorCode.LLM_CREDENTIAL_NOT_CONFIGURED] = 428
ERROR_STATUS[ErrorCode.LLM_CREDENTIAL_INVALID] = 400
ERROR_STATUS[ErrorCode.LLM_CREDENTIAL_DECRYPT_FAILED] = 500
```

### S1-03 428 在 `invoke` 内抛出会被吞掉（**最关键的架构错误**）

- **文档位置**：§4.1（L689-733）
- **实际情况**：`BaseAgent.invoke` 整体包在 `try/except Exception` 里（`backend/app/agents/base.py:169-303`），任何异常都被收敛为 `AgentResult(success=False)`；且 5 条链路都是 Celery 任务，HTTP 触发端点只返回 202（`app/services/*_service.py` 的 `enqueue_*`）。在 invoke 里抛 428 = **用户收 202 → 任务 failed**，AC-BK-01 的"428"永远测不出来。
- **修订**：分两层，HTTP 层负责 428，worker 层负责"兜底失败"。
  1. **HTTP 层**：新增依赖 `require_llm_credential`（`app/api/deps.py`），挂在 5 条链路的 6 个触发端点上（上传自动清洗也要挂）：

```python
# app/api/deps.py
async def require_llm_credential(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> User:
    """BYOK 守门：无用户 Key → 428；已标记 invalid → 400（不发任何 LLM 请求）。"""
    if not settings.BYOK_ENABLED or settings.ALLOW_SERVER_KEY_FALLBACK:
        return user
    credential = await credential_service.get_active_credential(session, user.id)
    if credential is None:
        raise LLMCredentialNotConfiguredError()
    if credential.status == "invalid":
        raise LLMCredentialInvalidError()
    return user
```

  2. **worker 层**：`invoke` 在 `try` **之前**解析凭据；无 Key 且 fallback 关时抛 `LLMCredentialNotConfiguredError`（不吞），由 `run_*_task` 的 `except Exception` 落 `task.status='failed'` + 可读 error_message（这是兜底，不是主路径）。此时**不写 llm_calls**（未发生调用）。

- **异步架构带来的口径约束（需求需知悉）**：AI 任务都是 Celery 异步执行，**首次** 401/402 只能发生在 worker → 任务 `failed` + 凭据标记 `invalid`；**下一次**触发时 HTTP 守门才返回 400。因此 AC-BK-07 的"返回可读 400"只能按"首次失败落任务错误 + 二次触发 400"验证，不能期望首次同步 400。若产品要求首次就同步提示，只能在触发端点前置做一次真实 verify（多一次 LLM 调用，不建议）。

- **挂载点**（6 处，均在 `backend/app/api/v1/`）：

| 端点 | 文件:行 | enqueue 点 |
|---|---|---|
| `POST /datasources/{id}/upload`（含自动清洗） | `datasources.py:152` | `datasources.py:234` |
| `POST /datasources/{id}/clean` | `datasources.py:251` | `datasources.py:285` |
| `POST /datasources/{id}/analyze/quality` | `analysis.py:38` | `analysis.py:67` |
| `POST /datasources/{id}/analyze/insights` | `analysis.py:142` | `analysis.py:162` |
| `POST /datasources/{id}/extract-knowledge` | `knowledge.py:31` | `knowledge.py:51` |
| `POST /datasources/{id}/reports` | `reports.py:29` | `reports.py:52` |

### S1-04 路由文件路径不存在

- **文档位置**：§2 文件清单（L101）、§3.6（L536）
- **问题**：`app/api/v1/users/` 不存在；`users` 是**单文件模块** `app/api/v1/users.py`（`/me`、`/me/password` 已在此）。新建同名目录会与模块冲突。
- **修订**：新建 `backend/app/api/v1/llm_credential.py`，路由不带 `/users` 前缀（在聚合处加）：

```python
# app/api/v1/__init__.py
from app.api.v1 import llm_credential
router.include_router(llm_credential.router, prefix="/users", tags=["凭据"])
```

### S1-05 `get_session` 不存在

- **文档位置**：§3.6（L553）
- **实际**：`app/api/deps.py` 只导出 `get_current_user` / `require_roles` / `assert_owner` / `get_token_payload`；会话依赖是 `app.core.database.get_db`。
- **修订**：`from app.core.database import get_db`；`user: User = Depends(require_roles("admin", "user"))`（GET 状态端点允许 `viewer`，因为需求 §3 要求 viewer 可查看自己是否配置）。

### S1-06 审计模型位置与 `resource_id` 类型错误

- **文档位置**：§3.5（L378、L514-525）
- **问题**：`app/models/audit_log.py` 不存在（实际在 `app/models/security.py`）；`resource_id` 是 `PG_UUID` 列，传 `str(user_id)` 会在绑定/序列化时报错；项目**没有任何审计写入先例**，action 命名没有现成常量可复用。
- **修订**：`from app.models.security import AuditLog`；`resource_id=user_id`（UUID 原值）；在 `credential_service.py` 内定义常量并补齐需求 §5 要求的事件：

```python
AUDIT_CREDENTIAL_CONFIGURED = "credential_configured"
AUDIT_CREDENTIAL_DELETED = "credential_deleted"
AUDIT_CREDENTIAL_INVALID = "credential_invalid"   # 需求 §5 可观测事件
# decrypt_failed 走日志/指标，不写库（解密失败时无法可信写库）
```

### S1-07 迁移 010 缺 `revision`/`down_revision`，文件名不符模板

- **文档位置**：§6.1（L1039-1043）
- **问题**：只写了 docstring，没有 `revision` / `down_revision` 变量 → Alembic 直接报错；且文件名 `010_seed_demo_account.py` 与 `alembic.ini` 模板不符。
- **修订**：统一用 `alembic revision -m "010 seed demo account"` 生成（产出 `20261028_HHMM_<rev>_010_seed_demo_account.py`），再填 `down_revision = "<009 的 revision>"`。

### S1-08 迁移 010 的 `cleaned_data` INSERT 与真实表结构不符（4 处硬伤）

- **文档位置**：§6.1（L1091-1103）
- **实际表结构**（`backend/app/models/datasource.py:141-195`）：`updated_at` **不存在**；`raw_data_id` NOT NULL（FK `raw_data.id`）；`timestamp` NOT NULL；`dialogue_id` 是 **UUID** 类型；`quality_score` 是 Float（0-100 有 CHECK）；且必须先有 `raw_data` 行。
- **修订**：demo 数据**不要放在迁移里**（见 S2-08），改由 `backend/scripts/seed_demo.py` 用 ORM 写；若坚持在迁移中插，最小正确形态是"先 raw_data 再 cleaned_data"：

```sql
-- 先 raw_data（raw_content 为 JSONB NOT NULL）
INSERT INTO raw_data (id, datasource_id, raw_content, status)
VALUES (:raw_id, :ds_id, '{"format":"txt","content":"demo"}'::jsonb, 'completed');
-- 再 cleaned_data（补齐 4 个必填列，UUID 用 gen_random_uuid()）
INSERT INTO cleaned_data
  (datasource_id, raw_data_id, dialogue_id, timestamp,
   user_message, ai_response, quality_score)
VALUES (:ds_id, :raw_id, gen_random_uuid(), NOW(), :um, :ar, :qs);
```

### S1-09 demo 密码哈希方式与项目约定冲突

- **文档位置**：§6.1（L1064）
- **问题**：直接用 `bcrypt.hashpw`；项目统一用 passlib `CryptContext(schemes=["bcrypt"])`（`app/core/security.py:22-26`），且 `006_seed_admin` 迁移的既定约定是"**不写占位密码哈希**，从环境变量读取"。
- **修订**：demo 密码支持 `SEED_DEMO_PASSWORD` 覆盖（默认 `demo123`），哈希用迁移内最小实现（迁移不应 import `app.core.security`，避免耦合运行时代码）：

```python
from passlib.context import CryptContext
_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
password = os.getenv("SEED_DEMO_PASSWORD", "demo123")
pw_hash = _pwd.hash(password)
```

生产环境建议 `SEED_DEMO_PASSWORD` 显式注入，避免公开仓库里的固定弱口令直接可用。

### S1-10 前端 `@/lib/api` 不存在，路径硬编码违反 A-1

- **文档位置**：§5.1（L808、L819-841）
- **实际**：axios 实例在 `frontend/src/api/client.js`（导出 `apiClient`）；项目规则 A-1："业务代码禁止散落字符串，所有路径进 `endpoints.js`"；且 query 调用统一封装在 `src/api/*.js` + `src/hooks/*.js`，组件不直接调 `apiClient`。另外 **`vite.config.js` 未配置 `@` 别名**，全项目都是相对导入，`@/lib/api` 双重不存在（既无别名、也无该文件）。
- **修订**：

```js
// src/api/endpoints.js —— users 下追加
llmCredential: '/users/me/llm-credential',
llmCredentialVerify: '/users/me/llm-credential/verify',
```

```js
// src/api/llmCredential.js
export async function getCredential() { /* apiClient.get(endpoints.users.llmCredential) */ }
export async function saveCredential(payload) { /* put */ }
export async function deleteCredential() { /* delete */ }
export async function verifyCredential(apiKey) { /* post */ }
```

组件只消费 `src/hooks/useLlmCredential.js` 暴露的 query/mutation。

### S1-11 登录页预填写法不存在

- **文档位置**：§5.4（L1019-1030）
- **实际**：`frontend/src/pages/Login/index.jsx` 用**单一 `form` 对象**（`const [form, setForm] = useState({ email: '', password: '' })`），没有 `setEmail`/`setPassword`；提交按钮是原生 `form` + `handleSubmit`。
- **修订**：`prefillDemo = () => setForm({ email: DEMO_EMAIL, password: DEMO_PASSWORD })`；演示账号常量集中在一处（如 `src/lib/demoAccount.js`），登录页与 Modal 的 demo 判断都引用它（见 S3-05）。

### S1-12 `cryptography` 未显式声明依赖

- **文档位置**：§3.2 直接 `from cryptography.fernet import ...`
- **实际**：`requirements.txt` 没有该包，仅由 `python-jose[cryptography]` 的 extras 间接安装；`python-jose` 换版本/去 extras 时 Fernet 直接 `ImportError`，也不符合依赖锁定与安全审计要求。
- **修订**：`requirements.txt` 显式加 `cryptography==<当前 venv 实装版本>`，并用 `pip freeze` 对齐；CI 的 `pip install -r requirements.txt` 会一起装上。

### S1-13 Pydantic validator 抛 `ValueError` 得到 422，不是需求要求的 400

- **文档位置**：§3.6（L569-584）用两个 `@field_validator`（`validate_key_format`、`reject_base_url_phase1`），失败即 `raise ValueError`
- **实际**：Pydantic 校验失败由 `validation_exception_handler` 统一转成 **422** + `VALIDATION_ERROR`（`app/core/errors.py:139-151`），而需求 FR-BK-02/02a 与 AC-BK-14 明确要求 `base_url` 非空返回 **400 `LLM_CREDENTIAL_INVALID`**；格式非法同样要求 400。
- **修订**：Schema 只做类型与基础约束，业务校验放到路由/服务层，抛 `LLMCredentialInvalidError`（400）：

```python
# schema：仅约束长度/类型，不做前缀语义
class CredentialIn(BaseModel):
    api_key: str = Field(min_length=12, max_length=256)
    base_url: str | None = None
    model: str | None = None

# 路由：
if body.base_url and body.base_url.strip():
    raise LLMCredentialInvalidError("Phase 1 不支持自定义端点（base_url 必须为空）")
if not _KEY_RE.match(body.api_key):
    raise LLMCredentialInvalidError("api_key 格式不符合要求（sk- 开头）")
```

### S1-14 `HTTPException(detail={...})` 的 detail 会被统一 handler 丢掉

- **文档位置**：§3.6（L616-622、L662-670）用 `HTTPException(status_code=400, detail={"code": ..., "message": ...})`
- **实际**：`http_exception_handler` 对非 401/403 的 `HTTPException` 一律映射为 `FrameworkErrorCode.HTTP_ERROR`，且 `detail` 不是字符串时 message 固定为 `"HTTP error"`（`app/core/errors.py:154-166`）——前端拿不到 `LLM_CREDENTIAL_INVALID`，`errorMessages.js` 的码值映射全部失效。
- **修订**：路由层**只抛领域异常**（`LLMCredentialInvalidError` / `LLMCredentialNotConfiguredError` / `RATE_LIMIT_EXCEEDED` 对应的 429 响应体），禁止用 `HTTPException` 携带业务码；`detail` 参数只允许字符串（框架级场景）。

---

## 3. S2 勘误：位置/链路错误（12 项，会导致返工）

### S2-01 成本过滤位置错

- **文档位置**：§4.3（L775-797）"找到 `degradation_middleware.py` 中计算当日成本的 SQL"
- **实际链路**：`DegradationMiddleware.dispatch` → `DegradationManager.get_level` → `get_cost_ratio` → `CostTracker.get_daily_cost()`（`app/core/cost_tracker.py:214-226`，且已有 `LlmCall.status == 'success'` 过滤）。
- **修订**：只改 `get_daily_cost`，加参数并默认仅统计服务端 Key；用量报表不要过滤：

```python
async def get_daily_cost(self, *, user_id=None, now=None, only_server_key: bool = True):
    stmt = select(func.coalesce(func.sum(LlmCall.total_cost), 0)).where(
        LlmCall.status == "success",
        LlmCall.created_at >= _day_start(now),
    )
    if only_server_key:
        stmt = stmt.where(LlmCall.key_source == "server")
    if user_id is not None:
        stmt = stmt.where(LlmCall.user_id == user_id)
    ...
```

`DegradationManager` 保持原调用（默认即生效）；`get_usage_stats` 不动。

### S2-02 `key_source` 不是"加一个字段"就完事，要贯穿 4 层

- **文档位置**：§4.2（L753-773）只给了 `LLMCall(...)` 的示意（项目里**不存在**手工构造 `LLMCall` 的地方）
- **实际链路**：`BaseAgent._track_success` / `_track_failure` → `CostTracker.track()` / `record_failure()` → `_upsert()` 的 `values` + `update_fields` → `LlmCall` 模型。少改任何一层，字段都会静默落默认值 `'server'`，用户 Key 调用照样触发降级（AC-BK-15 失败）。
- **修订清单**：
  1. `app/models/llm_call.py`：`key_source: Mapped[str] = mapped_column(String(10), nullable=False, server_default=text("'server'"))`；
  2. 迁移 009 加列（见 §6.7）；
  3. `CostTracker.track(..., key_source: str = "server")` 与 `record_failure(..., key_source: str = "server")`：写入 `values["key_source"]`；
  4. `_upsert` 的 `update_fields` 增加 `"key_source"`（幂等重试时会回写）；
  5. `BaseAgent._track_success` / `_track_failure` 增加参数透传（`key_source` 由 invoke 传入）；
  6. 对应测试断言 `llm_calls.key_source`。

### S2-03 Agent 注入点共 2 处，且不能只替换 chat

- **文档位置**：§4.1（L735 起"`self.llm` 全部改为 `agent_llm`"）
- **实际**：`base.py` 中 `self.llm` 有 2 处使用——`_call()` 里的 `self.llm.chat(...)`（L206）与结构化输出修复 `_parse_structured(..., llm=self.llm)`（L223）。**漏掉第二处**，结构化输出 repair 重试会混用服务端 Key（违反 FR-BK-11）。
- **修订**：invoke 内定义局部 `agent_llm`（默认 `self.llm`），两处都替换；`self.llm` 本身保留（构造期默认，供 `session is None` 的测试/POC 路径使用）。

### S2-04 `verify` 三宗罪：泄漏、异常分类不足、与 PUT 的关系没说清

- **文档位置**：§3.5（L481-496）、§3.6（L651-671）
- **问题**：
  1. `LLMClient(api_key=...)` 用完不 `aclose()`，`chat()` 首次调用会懒建 `httpx.AsyncClient`，连接泄漏；
  2. 只捕获 `LLMAuthenticationError`；实际 402 余额不足抛 `LLMQuotaError`、429 抛 `LLMRateLimitError`、400 抛 `LLMValidationError`（`app/core/llm.py:328-348`）——都会冒泡成 500 或未捕获异常，而需求要求"欠费/无效"都按不可用处理；
  3. 需求 D4 要求前端只有"验证并保存"一个操作，而文档同时保留独立 `POST /verify` 且前端不调用 → 端点存在但无消费方，需明确其定位（建议保留给"已配置后重新验证"，本期前端不用；避免保存时连打两次 LLM）。
- **修订**：

```python
async def verify(self, api_key: str) -> bool:
    try:
        async with LLMClient(api_key=api_key) as client:
            await client.chat(messages=[{"role": "user", "content": "hi"}], max_tokens=1)
        return True
    except LLMAuthenticationError:
        return False
    except LLMQuotaError:        # 402 余额不足：Key 格式没错但不可用
        return False
    except LLMError:             # 400/429/5xx：验证目的下均视为不可用
        return False
```

  另注：`max_tokens=1` 在 DeepSeek 上是否必然被接受需实测；若返回 400，可改为 `GET /models` 探测（需给 `LLMClient` 加只读方法，本期不阻塞）。

### S2-05 verify 限流是 TODO 桩

- **文档位置**：§3.6（L587-597，`_check_rate_limit` 全是注释）
- **实际可复用**：`app/core/redis.py:get_redis()`（懒加载 Redis）+ `app/middleware/rate_limit.py` 的固定窗口写法；错误码用现成的 `RATE_LIMIT_EXCEEDED`。
- **修订**：按用户维度固定窗口，`key = f"byok:verify:{user_id}:{window}"`，超限返回 429 + `Retry-After`；**注意** `tests/conftest.py:21` 默认关闭限流（`disable_rate_limit_by_default`），限流用例必须自行 `monkeypatch` 开启。

### S2-06 测试 fixture 名与目录不匹配

- **文档位置**：§6.2/§7（L1119-1246）
- **问题**：文档用例用 `session`、`client_a`、`client_b`、`saved_credential`、`user_with_credential` 等不存在的 fixture；`tests/e2e/` 目录不存在（E2E 在 `frontend/e2e/`，Playwright）。
- **修订**：集成用例基于 `tests/integration/conftest.py` 的 `db_session` / `client` / `test_user`（需要双用户时新建第二个 `User` 并各自登录取 token）；E2E 用例写到 `frontend/e2e/byok.spec.js`；`LLMClient(transport=httpx.MockTransport(...))` 的 mock 方式**可行**（构造函数支持 `transport`，`app/core/llm.py:157-165`），保留。

### S2-07 前端组件没有复用既有能力

- **文档位置**：§5.1（L846-924 自建 overlay/modal）
- **实际**：`src/components/Modal/Modal.jsx` 已封装 Radix Dialog（焦点陷阱、Esc、遮罩、`footer` 插槽）；`Input` / `Button` 组件也已存在。
- **修订**：`APIKeyModal` 用 `<Modal open onClose title="模型 API Key 设置" footer={...}>`；输入用 `Input`（`type` 切换明文/密文）、按钮用 `Button`；错误提示复用 `getErrorMessage(error)`。

### S2-08 迁移 010 的 demo 数据不可重置（文档 FAQ 自己承认了）

- **文档位置**：§6.1（L1090-1103）、§10 FAQ（L1327-1328）
- **问题**：迁移只跑一次，`ON CONFLICT DO NOTHING` 无法恢复被访客改掉的数据；FAQ 建议"在部署脚本里加 reset 逻辑"，但正文又放在迁移里，自相矛盾。
- **修订**：**职责拆开**——迁移 010 只创建 demo 账号（幂等 `ON CONFLICT (email) DO UPDATE`，密码由 `SEED_DEMO_PASSWORD` 环境变量提供）；demo 业务数据放 `backend/scripts/seed_demo.py`，支持 `--reset`（先按 demo 数据源 id 删除，再插入），部署脚本/entrypoint 每次调用。

### S2-09 前端用 email 硬编码判断 demo

- **文档位置**：§5.2（L958 `user?.email === 'demo@example.com'`）
- **修订**：常量集中到 `src/lib/demoAccount.js`（`DEMO_EMAIL` / `DEMO_PASSWORD`），UserMenu 与 Login 共用；不接受布尔 prop 多层透传。后续若后端返回 `is_demo` 再替换。

### S2-10 AI 触发按钮不是散点改造

- **文档位置**：§5.3（L970-996）示意 `AIActionButton`
- **实际**：5 条链路对应 6 个触发入口，分散在 `pages/Dashboard`、`pages/DataSources`、`pages/DataCleaning`、`pages/QualityAssessment`、`pages/KnowledgeBase`、`pages/Reports`。
- **修订**：抽一个 hook `useAiTriggerGuard()`（内部 `useLlmCredentialStatusQuery` + `openModal`），各页面只在 `onClick` 前调用 `guard(() => action())`；避免逐页复制 Modal 状态。

### S2-11 `BYOK_ENABLED=false` 的接口语义未定义

- **文档位置**：§3.6（L610-611 只给 PUT 返回 404）
- **修订**：开关矩阵统一（见 §5 的 DEC-09 表）：关闭时 GET 返回 `{"byok_enabled": false, "configured": false}`，PUT/DELETE/verify 返回 404（或直接不注册路由，二选一，需固定），前端菜单入口隐藏。

### S2-12 `llm_calls` 失败记录也要带 `key_source`

- **文档位置**：未提；§4.2 只覆盖成功路径
- **问题**：`BaseAgent._track_failure` 会写 `status='failed'` 行；不带 `key_source` 会落默认 `'server'`，把"用户 Key 调用失败"记成服务端 Key 调用，污染审计口径（虽不影响 `get_daily_cost`，因为只算 success）。
- **修订**：`_track_failure` 同样透传 `key_source`，测试断言失败行字段正确。

---

## 4. S3 勘误：口径与文档同步缺口（10 项）

| 编号 | 位置 | 问题 | 修订 |
|---|---|---|---|
| S3-01 | §7/§9（L1179、L1306） | "现有 479 用例 / 前端 323 用例 / E2E 8 条"——后端实测 **480（默认）/735（全量）**，前端静态 **301 声明**（each 展开更多），E2E 8 条正确 | AC-BK-12 改为"CI 全绿 + 覆盖率门槛达标 + E2E 全量通过"，数字不写死；若要写数字，写"默认 480 / 全量 735 / 前端 301+ / E2E 8" |
| S3-02 | §9 AC-BK-05（L1299） | 端点固定 `/users/me`，路由级越权不可达，文档自己承认"不存在路由级越权"，AC 却要求"返回 404"——写不出有意义的用例 | 改写为：① 不存在任何接受 user_id 参数的凭据端点（路由清单断言）；② admin 调凭据端点只拿到自己数据；③ 响应只含 `key_hint`，不含他人信息 |
| S3-03 | 需求文档 §6/§13/§16 | 需求写"迁移 008"，但 008 已被 `llm_calls_datasource_set_null` 占用；指南已改 009/010 | 回写需求文档为 009（建表+加列）/010（demo 账号）；同时提交当前未提交的 v0.3 改动 |
| S3-04 | §13 文档同步 | 架构文档**完全未同步**：API 设计无 428/无 3 码/无 4 端点章节；数据库设计无新表与 `key_source` | 按 §6.9 清单与代码同 PR 提交 |
| S3-05 | §5.2/§6.1 | 需求 §13 规定 demo 为"普通 user 角色"，但产品文案要"只读体验"；用 `role` 无法表达 | 明确：demo 保持 `role='user'`，只读感由"无 Key → AI 拦截"自然形成，不做角色特判（避免权限系统改造） |
| S3-06 | §3.2/§3.6 | `key_hint` 格式在 validator（长度≥12）与 `make_hint`（切片）两处各管一半 | 校验集中到 Pydantic schema（正则 `^sk-[A-Za-z0-9]{9,}$` 已隐含 ≥12），service 只负责切片，不再二次校验 |
| S3-07 | §3.5 | 只定义了 `credential_configured` / `credential_deleted`；需求 §5 还要求 `credential_invalid` / `decrypt_failed` 事件 | 补齐：前三个写 `audit_logs`，`decrypt_failed` 走 Loguru 结构化日志 + 指标（解密失败时不可信地写库） |
| S3-08 | §9 AC-BK-15 | 只断言 `llm_calls.key_source`，没断言"降级响应头不被用户 Key 触发" | 补一条集成用例：`key_source='user'` 的成本累积后，认证请求响应头 `X-Cost-Status` 仍为 `NORMAL`（`DegradationMiddleware` 写头） |
| S3-09 | §10 FAQ（L1315-1316） | 建议"不填 `CREDENTIAL_ENCRYPTION_KEY` + fallback=true"绕过——与 fail-closed 设计打架，容易误导开发 | 改为：本地调试用 `BYOK_ENABLED=false`（显式回退现状），`CREDENTIAL_ENCRYPTION_KEY` 必须配置；FAQ 重写 |
| S3-10 | §5.1/需求 §8 | 需求要求"Key 不写 localStorage/sessionStorage"，文档 Modal 只清 state，没提浏览器自动填充/密码管理器 | 补：`autoComplete="new-password"`（或 `one-time-code`）、`name` 不使用 `password` 语义、关闭时 `setKey('')`，并在测试中用 `queryByDisplayValue` 断言残留为空 |

---

## 5. 修订版关键设计决策（DEC）

| 编号 | 决策 | 结论 | 理由 / 影响 |
|---|---|---|---|
| DEC-01 | 错误码 | 新增 3 条：`LLM_CREDENTIAL_NOT_CONFIGURED`(428)、`LLM_CREDENTIAL_INVALID`(400)、`LLM_CREDENTIAL_DECRYPT_FAILED`(500)；废弃 `CREDENTIAL_CONFIG_ERROR` | 需求 §7 已定义，可回写 API 设计；避免"自造码"违规 |
| DEC-02 | 428 拦截位置 | HTTP 依赖 `require_llm_credential`（6 个触发端点；无 Key→428、已 invalid→400）+ worker `invoke` 前置兜底 | 428/400 语义属于"请求未被受理"，只能在 HTTP 层表达；worker 兜底保证并发删除 Key 时不静默用服务端 Key |
| DEC-03 | 成本隔离 | 只改 `CostTracker.get_daily_cost(only_server_key=True)`；用量报表不过滤 | 降级是唯一消费方（`DegradationManager`），改动面最小 |
| DEC-04 | `key_source` 透传 | 显式参数穿过 `BaseAgent → CostTracker.track/record_failure → LlmCall`，默认 `'server'` | 默认值保证存量测试不改也通过；失败行同样带值 |
| DEC-05 | verify 实现 | `async with LLMClient` + 捕获 `LLMError` 全族（401/402/429/400/5xx → 不可用） | 满足"欠费/无效都算不可用"；零连接泄漏 |
| DEC-06 | 限流 | Redis 固定窗口（复用 `get_redis`），用户维度，429 `RATE_LIMIT_EXCEEDED` + `Retry-After` | 与现有 `rate_limit.py` 一致，失败面小 |
| DEC-07 | demo 数据 | 迁移 010 建账号（密码 `SEED_DEMO_PASSWORD` 可覆盖）+ `scripts/seed_demo.py` 管业务数据（`--reset`） | 迁移可重放性 + 访客篡改可恢复 |
| DEC-08 | 前端分层 | `endpoints.js` → `api/llmCredential.js` → `hooks/useLlmCredential.js` → 组件（复用 `Modal`/`Input`/`Button`） | 符合 A-1 与 hooks 规范；便于测试与复用 |
| DEC-09 | 开关矩阵 | 见下表 | 消除 S2-11/S3-09 的语义空白 |
| DEC-10 | 审计 action | `credential_configured` / `credential_deleted` / `credential_invalid`；常量放 `credential_service` | 项目无先例，先定 3 个，后续加需同步数据库设计的审计章节 |

### DEC-09 开关矩阵（后端行为）

| `BYOK_ENABLED` | `ALLOW_SERVER_KEY_FALLBACK` | Agent 行为 | 凭据 API | 前端入口 |
|---|---|---|---|---|
| `true` | `false`（生产） | 有 Key → 用户 Key；无 Key → **428** | 全部可用 | 显示 |
| `true` | `true`（本地/CI） | 有 Key → 用户 Key；无 Key → 服务端 Key | 全部可用 | 显示 |
| `false` | `false` | 服务端 Key（回退现状） | PUT/DELETE/verify → 404；GET → `{byok_enabled:false}` | 隐藏 |

> 判定顺序固定：**先看 `BYOK_ENABLED`，再看 `ALLOW_SERVER_KEY_FALLBACK`**，与文档 §4.1 一致。

---

## 6. 修订版实施计划

### 6.1 阶段总览

| 阶段 | 内容 | 产出 | 门禁 | 预估 |
|---|---|---|---|---|
| M0 | 契约与基线（错误码、API/DB 文档、配置、依赖、需求文档回写） | 文档 + config + 依赖 | `pytest` 基线可跑、`alembic upgrade head` 通过 | 0.5 人日 |
| M1 | 加密服务 + 模型 + 迁移 009 + 凭据服务 + 4 API | 可用 API（curl 可测） | 单测 + 集成测试新增全绿；mypy/black/flake8 过 | 1.25 人日 |
| M2 | 6 处 HTTP 守门 + Agent 注入 + 成本隔离 | 428/Key 注入/成本隔离可用 | AC-01/02/07/08/15 通过；480 存量用例不回归 | 1.25 人日 |
| M3 | 前端 Modal/入口/引导/登录页 | 可交互闭环 | vitest 新增用例 + lint/format/coverage 过 | 1.0 人日 |
| M4 | demo 账号与数据、安全测试、E2E、文档同步 | 可演示 + 可交接 | 安全用例 + E2E 1 条 BYOK 链路；文档同步完成 | 1.0 人日 |
| **合计** | | | | **≈5.0 人日**（原估 3.25，增量来自勘误修复与门禁补齐，见 §6.10） |

### 6.2 M0：契约与基线

| ID | 任务 | 文件 | 要点 | 完成判据 |
|---|---|---|---|---|
| M0-1 | 需求文档回写并提交 | `docs/01-requirements/04-需求-用户自带LLM-API-Key（BYOK）.md` | §6 标题与 §13/§16 迁移编号改 009/010；保持 v0.3 并补 v0.3.1 变更记录 | 文档改动单独提交（当前已堆积未提交改动，先清理） |
| M0-2 | 错误码契约 | `docs/03-architecture/04-API设计.md` §12.1/§12.2 | 加 428；加 3 条码；补 4 端点章节（或新章节"BYOK 凭据"） | 评审通过 |
| M0-3 | 数据库契约 | `docs/03-architecture/03-数据库设计.md` | 新表 `user_llm_credentials`、`llm_calls.key_source`、审计 action 说明 | 与迁移设计一致 |
| M0-4 | 配置项 | `backend/app/core/config.py` + `backend/.env.example` | 4 项（`BYOK_ENABLED` / `CREDENTIAL_ENCRYPTION_KEY` / `ALLOW_SERVER_KEY_FALLBACK` / `LLM_CREDENTIAL_VERIFY_PER_MINUTE`）+ 注释；`.env.example` 头部声明"与 config 一一对应" | `python -c "from app.core.config import settings"` 可导入；如新增 `tests/unit/test_byok_config.py` 则纳入 M1 门禁 |
| M0-5 | 异常与错误码 | `app/core/errors.py`、`app/core/exceptions.py` | 3 码 + `ERROR_STATUS` + 3 个异常类 | `tests/unit/test_errors.py` 补用例 |
| M0-6 | 依赖声明 | `backend/requirements.txt` | `cryptography==<venv 实装版本>` | CI 安装通过 |
| M0-7 | 基线核验 | — | 跑 `pytest --collect-only` 记录数字；集成测试用 `docker-compose.test.yml` 起库 | 基线数字进 PR 描述 |

### 6.3 M1：存储层 + 加密 + 凭据 API

| ID | 任务 | 文件（精确路径） | 要点 |
|---|---|---|---|
| M1-1 | 加密服务 | `app/core/credential_encryption.py` | `encrypt` / `decrypt` / `make_hint`；密钥缺失抛 `LLMCredentialDecryptError`（fail closed，**不退化为明文**）；`InvalidToken` → 同错误；单测覆盖往返、掩码、密钥缺失、密文损坏 |
| M1-2 | ORM 模型 | `app/models/llm_credential.py` | 字段与需求 §6 一致；`user_id` UNIQUE；`status` 索引；`id` 用 `server_default=gen_random_uuid()`（与 `LlmCall` 风格一致）；注册到 `app/models/__init__.py`（否则 autogenerate 丢表） |
| M1-3 | User 关系 | `app/models/user.py` | `llm_credential = relationship(..., uselist=False, cascade="all, delete-orphan")`；注意 `User` 已有多个 relationship，需检查 `back_populates` 命名一致 |
| M1-4 | 迁移 009 | `migrations/versions/2026xxxx_<rev>_009_byok_credential_table.py` | `alembic revision -m "009 byok credential table"` 生成；建表 + `llm_calls.key_source`（`server_default='server'`，NOT NULL）；`downgrade` 对称；`alembic upgrade head` + `downgrade -1` 双向验证 |
| M1-5 | LlmCall 字段 | `app/models/llm_call.py` | 加 `key_source` 映射（与迁移一致） |
| M1-6 | 凭据服务 | `app/services/credential_service.py` | `get_active`（解密，失败抛解密错误）/ `get_active_credential`（返回 ORM 行，供 HTTP 守门判 status，不解密）/ `get_status`（不含明文）/ `upsert`（幂等，覆盖更新）/ `delete`（幂等）/ `verify`（见 DEC-05）/ `mark_invalid`（`UPDATE ... WHERE status != 'invalid'` 幂等）/ `_write_audit`（UUID + 3 个 action） |
| M1-7 | Pydantic Schema | `app/schemas/llm_credential.py` | `CredentialIn`：`api_key` 正则 + 长度；`base_url` 非空 → 422/400（注意：validator 抛 `ValueError` 是 422，需求要 400——**必须用自定义校验在路由层转 400**，或 `model_validator` 后路由捕获）；响应模型 `CredentialStatus` |
| M1-8 | 路由 | `app/api/v1/llm_credential.py` + `app/api/v1/__init__.py` | 4 端点；PUT 强制 verify（失败 400 `LLM_CREDENTIAL_INVALID` 且不入库）；GET 允许 viewer；DELETE 204；verify 限流；`BYOK_ENABLED=false` 按 DEC-09；`get_db`/`require_roles` 依赖正确 |
| M1-9 | 测试 | `tests/unit/test_credential_encryption.py`、`tests/integration/test_llm_credential_api.py` | 用 `db_session`/`client`/`test_user` fixture；monkeypatch `credential_service.verify` 避免真实网络；覆盖 AC-03/04/06/09/10/14 与限流（显式开启） |

**M1 门禁**：`pytest tests/unit/test_credential_encryption.py tests/integration/test_llm_credential_api.py -m "not prompt"` 全绿；`black/flake8/mypy` 干净；迁移可升级/可回滚。

### 6.4 M2：Agent 注入 + 成本隔离

| ID | 任务 | 文件 | 要点 |
|---|---|---|---|
| M2-1 | HTTP 守门 | `app/api/deps.py` + 6 处路由 | `require_llm_credential`；6 个触发端点挂 `dependencies=[Depends(require_llm_credential)]`（S1-03 表格） |
| M2-2 | invoke 前置解析 | `app/agents/base.py`（`try` 之前） | 参数校验后、`try` 前解析：`BYOK_ENABLED` + `user_id` + `session` 三者都有时查凭据；无凭据且 fallback 关 → 抛 `LLMCredentialNotConfiguredError`（**绝不发 LLM、不写 llm_calls**）；否则 `agent_llm = self.llm`、`key_source='server'` |
| M2-3 | agent_llm 替换 | `app/agents/base.py` L206、L223 | `self.llm.chat` → `agent_llm.chat`；`_parse_structured(llm=self.llm)` → `llm=agent_llm` |
| M2-4 | 鉴权失败处理 | `app/agents/base.py` | `except LLMAuthenticationError`：`key_source=='user'` 时 `mark_invalid` 幂等并 commit，抛 `LLMCredentialInvalidError`（worker 内最终体现为任务 failed + 可读 error_message）；其他异常保持原逻辑 |
| M2-5 | CostTracker 透传 | `app/core/cost_tracker.py` | `track` / `record_failure` 加 `key_source`；`values` 与 `_upsert.update_fields` 同步（S2-02） |
| M2-6 | 成本过滤 | `app/core/cost_tracker.py:get_daily_cost` | `only_server_key=True` 默认（S2-01）；`DegradationManager` 不改 |
| M2-7 | 测试 | `tests/integration/test_byok_agent_injection.py` | MockTransport 断言 `Authorization: Bearer <用户Key>`；无 Key → 428 + `call_count==0` + `llm_calls` 无行；fallback 双态；401 → invalid 幂等 + 400；双 `key_source` 降级门禁（含 `X-Cost-Status` 断言，S3-08） |

**M2 门禁**：AC-01/02/07/08/15 通过；默认 480 用例不回归；`mypy app` 干净。

### 6.5 M3：前端

| ID | 任务 | 文件 | 要点 |
|---|---|---|---|
| M3-1 | 路径常量 | `frontend/src/api/endpoints.js` | `users.llmCredential` / `users.llmCredentialVerify` |
| M3-2 | API 封装 | `frontend/src/api/llmCredential.js` | 4 个函数，返回 `data`，错误交给 `normalizeError` |
| M3-3 | Hooks | `frontend/src/hooks/useLlmCredential.js` | `credentialKeys = { all, status }`；`useCredentialStatusQuery`（`enabled` 控制）、`useSaveCredential`/`useDeleteCredential`（成功后失效 `credentialKeys.all`） |
| M3-4 | 错误文案 | `frontend/src/lib/errorMessages.js` + 其测试 | 3 条新码中文文案（"请先配置 API Key" / "API Key 无效" / "凭据解密失败，请联系管理员"） |
| M3-5 | 设置 Modal | `frontend/src/components/APIKeyModal/index.jsx` | 基于 `Modal`；显示/隐藏、已配置状态（hint/status/verified_at）、保存/删除/取消；保存中禁用；关闭与成功后清空 `key`；`autoComplete="new-password"` |
| M3-6 | 用户菜单入口 | `frontend/src/components/layout/UserMenu.jsx` | "API Key 管理" 菜单项 + Modal；demo 判断走 `src/lib/demoAccount.js` |
| M3-7 | 触发引导 | `frontend/src/hooks/useAiTriggerGuard.js` + 6 个触发点 | 未配置 → 打开 Modal（不禁用按钮）；已配置 → 执行原 action；demo 额外提示文案 |
| M3-8 | 登录页 | `frontend/src/pages/Login/index.jsx` | 演示账号提示 + 预填（`setForm`）；不自动提交 |
| M3-9 | 测试 | 对应 `*.test.jsx` | 状态渲染、显示/隐藏、保存成功清空、删除调用、未配置 guard 弹窗、登录页预填 |

**M3 门禁**：`npm run lint`（`--max-warnings 0`）、`npm run format:check`、`npm run test:coverage`（覆盖率阈值）、`npm run build`。

### 6.6 M4：演示数据 + 安全测试 + 文档同步

| ID | 任务 | 文件 | 要点 |
|---|---|---|---|
| M4-1 | 迁移 010 | `migrations/versions/2026xxxx_<rev>_010_seed_demo_account.py` | 只建 demo 账号：`ON CONFLICT (email) DO UPDATE SET password_hash = EXCLUDED.password_hash`（重放可恢复密码）；密码 `SEED_DEMO_PASSWORD` 可覆盖；`role='user'`、`is_verified=true`；`downgrade` 删 demo（**不删凭据表**） |
| M4-2 | demo 数据脚本 | `backend/scripts/seed_demo.py` | 幂等 + `--reset`；用 ORM 建 `data_sources` → `raw_data` → `cleaned_data` →（可选）`analysis_results`/`reports`；固定 UUID 便于重复执行；在 `scripts/docker-entrypoint.sh` 或部署文档中调用 |
| M4-3 | 安全测试 | `tests/security/test_byok_security.py` | ① 响应无明文（正则）；② 库内密文无 `sk-` 子串；③ admin 无他人凭据入口；④ 审计无 Key；⑤ `base_url` 非空 400 且无外呼（mock 断言）；⑥ 日志无明文（caplog 断言） |
| M4-4 | E2E | `frontend/e2e/byok.spec.js` | 打开菜单 → Modal → 输入非法 Key → 400 提示 → 删除/未配置态；**不调用真实付费 Key**（用 `ALLOW_SERVER_KEY_FALLBACK=true` 的 CI 配置或 mock 端点） |
| M4-5 | 文档同步 | 见 §6.9 | 与代码同 PR |
| M4-6 | 验收清单 | `docs/04-development/15-上线验收清单.md` | §1 端点计数 +4；§5 安全新增 BYOK 条目；§6 已知限制（demo 数据可被访客篡改，靠脚本重置） |

### 6.7 迁移规格（修订版）

**009（建表 + 加列）**：结构沿用 16 号文档 §3.4，但需修 3 点：
1. 文件用 `alembic revision` 生成（命名自动符合模板）；
2. `key_source` 列同时建议加复合索引，便于降级查询（可选）：`op.create_index("idx_llm_calls_key_source_date", "llm_calls", ["key_source", "created_at"])`；
3. `downgrade` 先删索引再删列/表，顺序与 upgrade 相反。

**010（demo 账号）**：只建账号，不插业务数据；`ON CONFLICT (email) DO UPDATE` 保证重放可恢复密码；`created_at/updated_at` 用 `NOW()`（`users` 表两列均存在，`deleted_at` 不填）。

### 6.8 测试矩阵（AC → 用例）

| AC | 层 | 测试文件 | 关键断言 |
|---|---|---|---|
| AC-01/08 | 集成 | `test_byok_agent_injection.py` | 无 Key + fallback 关 → 428（HTTP）/`LLMCredentialNotConfiguredError`（worker）、`call_count==0`、`llm_calls` 无行；fallback 开 → 服务端 Key |
| AC-02 | 集成 | 同上 | MockTransport 捕获 `Authorization` 为用户 Key |
| AC-03 | 集成 | `test_llm_credential_api.py` | 响应正则不命中、`key_hint` 前5后4 |
| AC-04 | 集成 | `test_byok_security.py` | 直接 SQL 查 `encrypted_api_key` 无 `sk-` |
| AC-05 | 安全 | 同上 | 路由清单无 user_id 参数端点；admin 只读自己 |
| AC-06 | 集成 | `test_llm_credential_api.py` | delete → 428；再 PUT → 200 |
| AC-07 | 集成 | `test_byok_agent_injection.py` | 401 → `status='invalid'` 幂等（并发两次只更新一次）；二次触发 HTTP 400；不回退服务端 Key |
| AC-09 | 单元 | `test_credential_encryption.py` | 密钥缺失 → 错误、库无明文 |
| AC-10 | 集成 | `test_llm_credential_api.py` | 第 6 次 verify → 429（显式开启限流） |
| AC-11 | 安全 | `test_byok_security.py` | `audit_logs` 有记录、`details::text` 无 Key |
| AC-12 | 回归 | CI | 默认 480 + 前端全量 + E2E 8 条 + 覆盖率门槛 |
| AC-13 | 集成 | `test_byok_agent_injection.py` | 老用户无凭据登录/浏览 200 |
| AC-14 | 安全 | `test_byok_security.py` | `base_url` 非空 → 400；MockTransport 断言 0 次外呼 |
| AC-15 | 集成 | `test_byok_agent_injection.py` | `llm_calls.key_source='user'`；用户 Key 成本累积后 `X-Cost-Status: NORMAL`；服务端 Key 仍降级 |

### 6.9 文档同步清单（与代码同 PR）

| 文档 | 章节 | 改动 |
|---|---|---|
| `docs/01-requirements/04-...BYOK.md` | §6、§13、§16 | 迁移 008 → 009/010；提交当前未提交改动 |
| `docs/03-architecture/04-API设计.md` | §12.1、§12.2、新端点章节 | 加 428；加 3 条码；补 4 个端点（请求/响应/错误） |
| `docs/03-architecture/03-数据库设计.md` | 新表章节 + `llm_calls` | `user_llm_credentials` DDL、`key_source`、审计 action 说明 |
| `docs/05-design/03-页面设计规范.md` | 组件/交互 | API Key Modal、未配置引导、演示账号提示 |
| `docs/04-development/15-上线验收清单.md` | §1、§5、§6 | 端点计数、安全项、已知限制 |
| `docs/04-development/16-BYOK开发指南.md` | 顶部提示 + 按 §9 附录逐节 | 加"实施以 17 号为准"提示；S1/S2 章节按本文件修订 |
| `backend/.env.example` | BYOK 段 | 4 项 + 说明（与 config 一一对应） |

### 6.10 工时重估

| 阶段 | 16 号原估 | 修订估 | 增量原因 |
|---|---|---|---|
| M1 | 1.0 | 1.25 | 错误码/异常/迁移命名与列修正、路由路径修正、依赖声明 |
| M2 | 1.0 | 1.25 | 428 改为 6 处 HTTP 守门 + worker 兜底、key_source 四层透传 |
| M3 | 0.75 | 1.0 | 前端分层（endpoints/api/hooks/组件复用）+ errorMessages + 覆盖率 |
| M4 | 0.5 | 1.0 | demo 数据脚本化（ORM 建 4 张表）+ E2E + 文档同步 |
| 合计 | 3.25 | **5.0** | 勘误修复与质量门禁补齐 |

---

## 7. 修订版验收口径（AC-BK-01~15）

> 相对 16 号文档 §9 的变化：AC-05 改写、AC-12 去数字化、AC-15 增强度头断言，其余保持但补"测试文件"为真实路径。

| 编号 | 验收标准（修订） | 测试文件 |
|---|---|---|
| AC-BK-01 | 无 Key + fallback 关：HTTP 触发 AI 操作 → 428 `LLM_CREDENTIAL_NOT_CONFIGURED`；无任何外部 LLM 请求；无 `llm_calls` 记录 | `tests/integration/test_byok_agent_injection.py` |
| AC-BK-02 | 配置 Key 后任一 Agent 调用 → `Authorization: Bearer <用户Key>`，非服务端 Key | 同上 |
| AC-BK-03 | GET 响应正则 `sk-[A-Za-z0-9]{10,}` 不命中；仅 `key_hint`（前5+…+后4） | `tests/integration/test_llm_credential_api.py` |
| AC-BK-04 | 库内 `encrypted_api_key` 不含明文子串 | `tests/security/test_byok_security.py` |
| AC-BK-05 | （改写）不存在接受他人 user_id 的凭据端点；admin 只能读写自己的凭据；GET 仅返回本人字段 | 同上 |
| AC-BK-06 | 删除后 AI 操作恢复 428；再配置后恢复可用 | `tests/integration/test_llm_credential_api.py` |
| AC-BK-07 | 无效 Key：verify 400；worker 调用 401 → 标记 `invalid`（幂等 `WHERE status != 'invalid'`）且不回退服务端 Key；**下次触发时 HTTP 层 400**（首次因异步无法同步 400，见 S1-03 口径约束） | `test_byok_agent_injection.py`（含并发用例） |
| AC-BK-08 | fallback 双态：开 → 服务端 Key 行为同现状；关 → 绝不回退 | 同上 |
| AC-BK-09 | `CREDENTIAL_ENCRYPTION_KEY` 缺失 → 保存失败（500 `LLM_CREDENTIAL_DECRYPT_FAILED`），无明文入库 | `tests/unit/test_credential_encryption.py` |
| AC-BK-10 | verify > 5 次/分钟/用户 → 429 `RATE_LIMIT_EXCEEDED` | `tests/integration/test_llm_credential_api.py` |
| AC-BK-11 | 设置/删除写 `audit_logs`（`credential_configured`/`credential_deleted`），无 Key 值 | `tests/security/test_byok_security.py` |
| AC-BK-12 | 回归门禁：后端默认 480 + 全量 735 不新增失败、前端全量、E2E 8 条、覆盖率门槛（后端 80 / 前端 80/70） | CI |
| AC-BK-13 | 老用户/种子账号迁移后登录、只读浏览正常 | `test_byok_agent_injection.py` |
| AC-BK-14 | 非空 `base_url` → 400 `LLM_CREDENTIAL_INVALID`；MockTransport 断言无外呼 | `tests/security/test_byok_security.py` |
| AC-BK-15 | 用户 Key 调用 `key_source='user'` 不触发降级（`X-Cost-Status: NORMAL`）；服务端 Key 调用仍受 `DAILY_COST_LIMIT` | `test_byok_agent_injection.py` |

---

## 8. 需要你拍板的 4 项

| # | 问题 | 选项 | 建议 |
|---|---|---|---|
| 1 | 错误码落地方式 | A. 新增 3 条业务码并回写 API 设计（改动两处文档）B. 只加 428 + 复用 `INTERNAL_ERROR`/`RATE_LIMIT_EXCEEDED`（前端无法区分"未配置"） | **A**（需求 §7 已定，AC-01/09 依赖它） |
| 2 | verify 探测方式 | A. `chat(max_tokens=1)`（已实现，零改动，可能产生 1 token 费用）B. 新增 `GET /models` 探测（零 token，需实测 DeepSeek 兼容性与新代码） | **A**（当前最稳；B 作为 Phase 2 优化项） |
| 3 | demo 数据承载 | A. 迁移只建账号 + 脚本 seed 业务数据（可重置）B. 全部放迁移（一次性，不可重置） | **A**（S2-08） |
| 4 | 本轮是否含 M3 前端 | A. 含（需求 D1 要求"按钮可点弹 Modal"）B. 仅后端 + API，前端下轮 | **A**（否则 AC-03/06/12 与演示账号无法验收） |

---

## 9. 附录：16 号文档逐节处置索引

> 状态：下表处置已于 2026-10-28 **全部应用到 16 号 v2.0**（见其 §11 变更记录）；本表保留为差异对照，便于复核修订是否遗漏。

| 16 号章节 | 行号（v1.0） | 处置 | 关联勘误 |
|---|---|---|---|
| §1 前置阅读 | L26-51 | 保留；"迁移 008"改"008 已占用，下一个 009" | S3-03 |
| §2 架构总览 | L55-124 | 数据流（保存/调用）保留；**"调用"流改为 HTTP 守门 + worker 兜底两层图**；文件清单按本文件 §6 修订 | S1-03/S1-04 |
| §3.1 config | L130-152 | 保留 4 项；补 `.env.example` 与"配置事实源"声明 | M0-4 |
| §3.2 加密服务 | L156-215 | 保留算法与掩码；**异常构造改子类**；删 `CREDENTIAL_CONFIG_ERROR` | S1-01/S1-02 |
| §3.3 模型 | L219-291 | 保留；补 `__init__.py` 注册位置说明（已有） | — |
| §3.4 迁移 009 | L293-349 | 保留主体；`alembic revision` 生成；补索引与 downgrade 顺序 | S1-07 / §6.7 |
| §3.5 凭据服务 | L353-529 | 保留结构；`verify` 改 `async with` + `LLMError` 全族；审计表路径/类型/UUID 修正；补齐 3 个 action | S1-06/S2-04/S3-07 |
| §3.6 路由 | L533-679 | **路径改 `app/api/v1/llm_credential.py`**；`get_db`/`require_roles`；`base_url` 400 的转换位置（`ValueError` 是 422）；禁用 `HTTPException(detail={...})`；限流实现；BYOK_ENABLED=false 语义 | S1-04/S1-05/S1-13/S1-14/S2-05/S2-11 |
| §4.1 Agent 注入 | L685-751 | **只保留"解析+构造 agent_llm"部分；428 移到 HTTP 依赖**；补 `_parse_structured` 替换 | S1-03/S2-03 |
| §4.2 llm_calls | L753-773 | 改为"改 `CostTracker.track/record_failure` + model + 迁移"，删手工 `LLMCall(...)` 示例 | S2-02 |
| §4.3 降级过滤 | L775-797 | 改文件：`app/core/cost_tracker.py:get_daily_cost`，加 `only_server_key` 参数 | S2-01 |
| §5.1 Modal | L803-926 | 基于 `components/Modal`；路径/数据获取走 endpoints/api/hooks；`autoComplete` 与清空策略 | S1-10/S2-07/S3-10 |
| §5.2 UserMenu | L928-963 | 保留交互；demo 判断走常量模块，不硬编码 email | S2-09 |
| §5.3 AI 按钮 | L965-996 | 改为统一 `useAiTriggerGuard`，覆盖 6 个触发点 | S2-10 |
| §5.4 登录页 | L998-1031 | 预填写法改 `setForm`；常量集中 | S1-11 |
| §6.1 迁移 010 | L1037-1112 | **只建账号**；补 revision 变量；bcrypt 改 passlib + env 覆盖；业务数据移到脚本 | S1-07/S1-08/S1-09/S2-08 |
| §6.2 安全测试 | L1114-1158 | 保留断言；fixture 改 `db_session`/`client`；补日志/无外呼断言 | S2-06 |
| §7 测试策略 | L1162-1246 | 保留 MockTransport 方案；用例数改 CI 口径；补覆盖率/质量门禁 | S3-01 |
| §8 配置参考 | L1250-1288 | 保留；CI 段补"前端不依赖真实 Key"说明；生产段加"Secret 备份交接" | — |
| §9 AC 表 | L1291-1310 | 按本文件 §7 整表替换 | S3-02/S3-08 |
| §10 FAQ | L1313-1331 | 重写 Q1（用 `BYOK_ENABLED=false` 调试）；Q2 保留；Q3-Q5 保留；Q6 补"迁移 010 只建账号" | S3-09 |

---

## 10. 变更记录

| 版本 | 日期 | 变更摘要 |
|---|---|---|
| v1.0 | 2026-10-28 | 首版：基于 `main@f170192` 全量核验，产出 14 项 S1、12 项 S2、10 项 S3 勘误，以及 M0–M4 修订版实施计划、迁移规格、测试矩阵、文档同步清单、AC 修订口径与 4 项待拍板决策 |
| v1.1 | 2026-10-28 | 4 项待拍板决策按推荐全部采纳（A/A/A/A）；16 号文档已按本文修订为 **v2.0**；本文转为"勘误依据与决策记录"，§9 附录改为差异对照 |
| v1.2 | 2026-10-28 | 16 号 v2.0 经独立对抗性校验后又发现 9 个 A 级/11 个 C 级问题（契约测试同步、测试环境 fallback、aware datetime、脚本 bootstrap、审计幂等、无障碍等），已并入 16 号 **v2.1**（见其 §11 变更记录） |
| v1.3 | 2026-10-28 | 业务收敛拍板（[BYOK-业务收敛-v1](../07-review/BYOK-业务收敛-v1.md) §12）：16 号升 **v2.2**（工时 4.2、全局 428、demo 5 页种子、E2E 延后、verify 保留口径），需求文档升 **v0.4**（迁移 009/010、D6~D11、演示验收口径）；本文作为勘误依据维持不变 |
| v1.4 | 2026-10-28 | 实现落地：迁移实拆 **009 建表 / 010 `key_source` / 011 demo 账号**；16 号升 **v2.3**、需求升 **v0.4.1**；后端 4 端点+审计+`key_source`、前端 M3、CI/env、demo 种子脚本完成，`tests/unit` + BYOK 集成测试通过 |
