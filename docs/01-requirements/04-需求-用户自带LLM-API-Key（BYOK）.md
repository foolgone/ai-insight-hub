# 需求：用户自带 LLM API Key（BYOK）

> **文档版本**：v0.1（草稿，待确认）  
> **创建日期**：2026年10月27日  
> **文档状态**：草稿 —— 需求已澄清，3 个待拍板项见 §17  
> **需求编号**：BYOK-2026-10  
> **提出背景**：项目作为作品集公网开放体验时，若所有访客共用部署者的 `DEEPSEEK_API_KEY`，存在被刷爆、成本不可控的风险  
> **关联文档**：[01-项目现状与待办清单](../07-review/01-项目现状与待办清单.md)、[04-API设计](../03-architecture/04-API设计.md)、[03-数据库设计](../03-architecture/03-数据库设计.md)、[05-页面设计规范](../05-design/03-页面设计规范.md)、[15-上线验收清单](../04-development/15-上线验收清单.md)

---

## 1. 背景与问题

### 1.1 现状

| 项 | 现状 |
| --- | --- |
| LLM Key | 服务端全局一份：`backend/.env` 的 `DEEPSEEK_API_KEY`，所有用户共用（[llm.py L154-L166](../../backend/app/core/llm.py#L154-L166)） |
| 调用鉴权 | 用户通过 JWT 登录；但所有用户的 AI 调用都消耗部署者的 Key |
| 成本防护 | IP 限流 60/min、按**单用户**日成本降级（`DAILY_COST_LIMIT`）、月度预算未实现；`LLM_PRICE_*` 默认 0 时降级不触发 |
| 公网风险 | 注册端点匿名开放；攻击者可批量注册、触发清洗/评估/提取/报告任务，持续消耗部署者余额 |

### 1.2 为什么选择 BYOK

- **成本归位**：每个用户用自己的 DeepSeek 账号付费，部署者不再承担不可控的 AI 成本；
- **无刷爆风险**：Key 由用户持有，泄露/滥用影响的是用户自己的账户；
- **产品形态更真实**：作品集展示"多租户 + 凭据管理 + 加密存储 + 安全边界"，比"共享 Key + 限流"更接近生产级 SaaS；
- **可扩展**：为未来多 provider（OpenAI 兼容端点）、团队共享凭据留出结构。

### 1.3 方案对比

| 方案 | 成本风险 | 用户感知 | 安全面 | 结论 |
| --- | --- | --- | --- | --- |
| A. 共享服务端 Key + 限流/配额 | 高（可被多账号/多 IP 绕过） | 开箱即用 | Key 不出服务端 | 仅作兜底/演示账号 |
| B. **用户自带 Key（BYOK，本需求）** | **无（用户自付）** | 需一次性配置 | 需处理加密与回显 | **采纳** |
| C. 前端 localStorage 存 Key、每次请求带 Header | 无 | 配置简单 | ❌ XSS 可直接窃取、每请求泄露、无法审计 | 不采纳 |

---

## 2. 目标与非目标

### 2.1 目标

1. 每个登录用户可**安全地配置/更新/删除自己的 LLM API Key**；
2. 用户触发 AI 任务时，系统**优先使用用户自己的 Key**，不消耗服务端 Key；
3. 未配置 Key 的用户仍可**只读浏览**，AI 操作被明确引导与拦截；
4. Key 加密落库、接口不回明文、日志不泄露、越权不可读；
5. 开发/CI/E2E 环境可通过开关继续使用服务端 Key（不阻塞现有测试）；
6. 现有 5 条 Agent 链路、成本追踪、降级机制不回归。

### 2.2 非目标（本需求不做）

- 多 provider 完整适配（OpenAI/Claude/Azure 等）——字段预留，首批仅 DeepSeek；
- 团队/组织级共享 Key、Key 池、按项目配额分配；
- 用户 Key 的用量账单/发票/充值能力（DeepSeek 平台承担）；
- 用户中心完整改版（仅新增 API Key 设置弹窗）；
- 服务端代理转发用户 Key 之外的模型路由/负载均衡。

---

## 3. 用户角色与场景

| 角色 | 场景 | 期望结果 |
| --- | --- | --- |
| 新用户（user） | 注册后首次进入 Dashboard | 看到"未配置 API Key"引导；可浏览预置/自有数据，AI 按钮提示先配置 |
| 已配置用户 | 打开设置，粘贴 Key，点击测试 | 校验通过后保存；状态显示 `sk-…a1b2` 掩码；AI 操作可用 |
| 已配置用户 | Key 失效/欠费 | AI 调用返回明确错误码；凭据标记 `invalid`；引导更新 |
| 已配置用户 | 更换/删除 Key | 覆盖更新或删除；删除后 AI 操作恢复拦截 |
| 只读用户（viewer） | 浏览数据/报告 | 不触发 AI，无需 Key；可查看自己是否已配置 |
| 部署者 | 公网作品集 | 服务端 Key 不参与真实用户调用；成本可控 |
| 管理员（admin） | 查看任意用户 | **不可读取他人 Key**（仅本人可管理） |
| 开发/测试 | CI/E2E/本地 | `ALLOW_SERVER_KEY_FALLBACK=true` 时沿用服务端 Key，测试不依赖真实 Key |

---

## 4. 功能需求

> 优先级：P0 = 本需求必须；P1 = 建议同期；P2 = 后续。

### 4.1 凭据管理

| 编号 | 需求 | 优先级 | 验收要点 |
| --- | --- | --- | --- |
| FR-BK-01 | 用户可新增/更新自己的 LLM API Key（`PUT /users/me/llm-credential`） | P0 | 保存成功返回 `configured=true` 与掩码；重复提交为覆盖更新 |
| FR-BK-02 | Key 至少进行格式校验（非空、长度、`sk-` 前缀等，以 DeepSeek 实际格式为准） | P0 | 非法格式 400 `LLM_CREDENTIAL_INVALID` |
| FR-BK-02a | Phase 1 仅支持 DeepSeek 官方端点；`base_url` 字段传入非空值时**直接拒绝**（400），防止 SSRF（详见 §15）；Phase 2 开放自定义端点时须加 URL 白名单与私网过滤 | P0 | 非空 `base_url` 返回 400 `LLM_CREDENTIAL_INVALID` |
| FR-BK-03 | 保存前可选做连通性校验（`POST .../verify`） | P1 | 有效返回 `{valid:true}`；无效返回 400；该端点限流（≤5 次/分钟/用户）；verify 发起的 LLM 调用**不写 `llm_calls`、不计成本**（属验证行为非业务调用） |
| FR-BK-04 | 查询自身配置状态（`GET /users/me/llm-credential`） | P0 | 仅返回 `configured/key_hint/status/verified_at`，**不含明文/密文**；`key_hint` 固定格式为「前 5 位 + `…` + 后 4 位」（如 `sk-x…a1b2`），Key 长度 < 12 位视为格式非法 |
| FR-BK-05 | 删除自身 Key（`DELETE /users/me/llm-credential`） | P0 | 204；删除后 AI 操作恢复 428 |
| FR-BK-06 | 同一用户仅保留一条有效凭据（`user_id` 唯一） | P0 | 重复新增为覆盖；数据库唯一约束兜底 |

### 4.2 Agent 调用

| 编号 | 需求 | 优先级 | 验收要点 |
| --- | --- | --- | --- |
| FR-BK-07 | 5 条 Agent 链路（清洗/评估/提取/洞察/报告）在 `invoke` 前按 `user_id` 解析用户凭据 | P0 | 调用 LLM 时 `Authorization` 为用户 Key（mock transport 断言） |
| FR-BK-08 | 未配置 Key 且 fallback 关闭时，AI 操作返回 **428 `LLM_CREDENTIAL_NOT_CONFIGURED`**，不调用外部 API、不写 `llm_calls` | P0 | 断言无 LLM 请求、无成本记录、错误码正确 |
| FR-BK-09 | 用户 Key 无效（401/鉴权失败）时返回可读错误（400/422），并将凭据标记 `invalid`；**不自动回退服务端 Key** | P0 | 不产生服务端 Key 调用；状态为 `invalid`；前端提示更新；并发任务同时标记时须幂等（`UPDATE ... WHERE status != 'invalid'`），避免重复触发后续副作用 |
| FR-BK-10 | `ALLOW_SERVER_KEY_FALLBACK=true` 时，无凭据用户回退服务端 Key（仅开发/CI/演示账号） | P0 | 开关关闭时不得回退；开关打开时行为与现状一致 |
| FR-BK-11 | 结构化输出 repair 重试复用同一用户凭据，不混用 Key | P1 | 重试请求的 Authorization 仍为用户 Key |

### 4.3 状态与引导

| 编号 | 需求 | 优先级 | 验收要点 |
| --- | --- | --- | --- |
| FR-BK-12 | 未配置用户在 Dashboard/相关页面看到引导提示；AI 触发按钮禁用或点击弹设置 | P0 | 文案明确、可直达设置弹窗 |
| FR-BK-13 | 设置弹窗支持显示/隐藏、测试连接、保存、删除；保存后清空输入并显示掩码 | P0 | 手动/自动化用例覆盖 |
| FR-BK-14 | 凭据状态变化后（保存/删除）前端刷新状态，无需重新登录 | P0 | AI 按钮状态即时变化 |

### 4.4 安全与审计

| 编号 | 需求 | 优先级 | 验收要点 |
| --- | --- | --- | --- |
| FR-BK-15 | Key 加密落库（应用层 Fernet/AES-GCM），数据库中不含明文子串 | P0 | SQL 查询断言密文不含 `sk-` 原始值 |
| FR-BK-16 | 接口/日志/异常信息**永不返回或打印明文 Key**；仅回显 `key_hint`（如 `sk-…a1b2`） | P0 | 响应与日志正则断言不含完整 Key |
| FR-BK-17 | 仅本人可管理自己的凭据；admin 亦不可读他人；越权访问返回 404（不暴露存在性） | P0 | 跨用户/跨角色用例 |
| FR-BK-18 | 设置/删除 Key 写入 `audit_logs`（事件类型、时间、user_id；不含 Key 值） | P1 | 审计记录存在且无敏感值 |
| FR-BK-19 | 加密密钥 `CREDENTIAL_ENCRYPTION_KEY` 缺失时**拒绝保存**（fail closed），不退化为明文存储 | P0 | 缺少密钥时 500/配置错误，且无明文入库 |

### 4.5 兼容与运维

| 编号 | 需求 | 优先级 | 验收要点 |
| --- | --- | --- | --- |
| FR-BK-20 | `BYOK_ENABLED=false` 时整体回退现状（服务端 Key，无设置入口） | P1 | 开关行为可测 |
| FR-BK-21 | 老用户/种子账号无凭据时保持只读可用，不因迁移报错 | P0 | 迁移后登录/浏览正常 |
| FR-BK-22 | 提供凭据状态/加密失败的可观测日志与指标（不含敏感值） | P1 | 日志字段可检索 |

---

## 5. 非功能需求

| 类别 | 要求 |
| --- | --- |
| 安全 | TLS 传输；加密存储；最小权限；不回显；审计；verify 限流；错误信息脱敏；Phase 1 拒绝非空 `base_url`（SSRF 防护，Phase 2 开放时须加白名单） |
| 性能 | 凭据读取 ≤1 次 DB 查询/Celery 任务（任务启动时一次性解密，同一任务内复用；不在 HTTP 请求层面缓存）；加解密开销可忽略（亚毫秒级） |
| 可用性 | 凭据服务异常时 AI 操作失败要"明确报错"而非静默用服务端 Key |
| 兼容性 | 不影响现有 JWT 认证、5 Agent、成本追踪、降级、SSE、报告导出；用户 Key 调用的估算成本写入 `llm_calls`（`key_source='user'`）但**不纳入** `DAILY_COST_LIMIT` 降级计算（降级只统计 `key_source='server'` 的调用） |
| 可观测 | 记录 `credential_configured` / `credential_invalid` / `decrypt_failed` 事件（无敏感值） |
| 隐私 | 不采集 Key 以外的用户凭据；不向第三方共享 |

---

## 6. 数据模型（迁移 008）

新增表 `user_llm_credentials`（不采用在 `users` 加列，便于扩展 provider）：

```sql
CREATE TABLE user_llm_credentials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL DEFAULT 'deepseek',
    base_url VARCHAR(500),                      -- 预留：Phase 2 OpenAI 兼容端点；Phase 1 保存时若非空则拒绝
    model VARCHAR(100),                         -- 预留：模型覆盖
    encrypted_api_key TEXT NOT NULL,            -- Fernet 密文（不存明文）
    key_hint VARCHAR(20) NOT NULL,              -- 固定格式：前5位 + … + 后4位，如 sk-x…a1b2
    status VARCHAR(20) NOT NULL DEFAULT 'active',  -- active / invalid
    verified_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_user_llm_credentials_status ON user_llm_credentials(status);
```

现有 `llm_calls`（或 `analysis_results` 的成本字段）须新增 `key_source VARCHAR(10) NOT NULL DEFAULT 'server'`（取值 `'server'` / `'user'`）：

- `key_source='user'`：用户自带 Key 的调用，估算成本**只记录不计入降级阈值**；
- `key_source='server'`：服务端 Key 的调用，计入 `DAILY_COST_LIMIT` 降级逻辑（与现有行为一致）。

> 此字段通过 Alembic 在迁移 008 中同步添加；存量记录默认值 `'server'`，无需回填业务逻辑。

加密说明：

- 加密算法：**Fernet**（AES-128-CBC + HMAC-SHA256，`cryptography` 库标准实现）；
- 加密密钥：环境变量 `CREDENTIAL_ENCRYPTION_KEY`（32 字节 base64；生成命令见 §10）；
- **密钥轮换（Phase 1 不支持）**：当前版本使用单密钥，密钥一旦丢失已存凭据不可恢复（见 §15 风险）；Phase 2 采用 `MultiFernet` 多密钥方案实现零停机轮换，届时需评审迁移脚本；
- 迁移仅建表 + 加字段，不改 `users`；旧数据无需回填凭据。

---

## 7. 接口需求

> 均为 JWT 保护，只操作当前登录用户；响应不返回明文 Key。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `PUT` | `/api/v1/users/me/llm-credential` | 新增/更新 |
| `GET` | `/api/v1/users/me/llm-credential` | 查询状态 |
| `DELETE` | `/api/v1/users/me/llm-credential` | 删除 |
| `POST` | `/api/v1/users/me/llm-credential/verify` | 连通性测试（限流） |

**PUT 请求**：

```json
{ "api_key": "sk-xxxxxxxx", "base_url": null, "model": null }
```

> ⚠️ Phase 1：`base_url` 传入非空值直接返回 400 `LLM_CREDENTIAL_INVALID`（SSRF 防护）；`model` 字段当前忽略，保留作 Phase 2 扩展。

**PUT/GET 响应**：

```json
{
  "configured": true,
  "provider": "deepseek",
  "key_hint": "sk-…a1b2",
  "status": "active",
  "verified_at": "2026-10-27T12:00:00Z"
}
```

**错误码**：

| 错误码 | HTTP | 场景 |
| --- | --- | --- |
| `LLM_CREDENTIAL_NOT_CONFIGURED` | 428 | 无 Key 且 fallback 关闭时触发 AI 操作 |
| `LLM_CREDENTIAL_INVALID` | 400 | 格式非法 / verify 失败 |
| `LLM_CREDENTIAL_DECRYPT_FAILED` | 500 | 加密密钥不匹配（内部错误，日志脱敏） |
| `RATE_LIMIT_EXCEEDED` | 429 | verify/设置频率超限 |

---

## 8. 页面与交互需求

- **入口**：Header 用户菜单（[UserMenu.jsx](../../frontend/src/components/layout/UserMenu.jsx)）新增「API Key 设置」，点击打开 Modal（不新建页面，控制改动面）；
- **Modal 内容**：
  - 标题「模型 API Key 设置」+ 说明「Key 仅加密保存在本系统，用于调用 DeepSeek，不会明文回显」+ 获取地址链接；
  - 输入框（password 类型、显示/隐藏切换、`autocomplete="off"`、粘贴提示）；
  - 按钮：测试连接 / 保存 / 删除（已配置时）；
  - 已配置状态：显示 `key_hint`、状态徽章（正常/无效）、最近验证时间；
- **未配置引导**：Dashboard 顶部 Banner「配置自己的 API Key 后即可使用 AI 清洗/评估/提取/报告」+「去配置」按钮；AI 触发按钮禁用并显示 tooltip；
- **错误提示**：未配置（引导配置）、无效 Key（更新 Key）、服务异常（稍后重试）、限流（稍后再试）；
- **安全**：Key 不写入 localStorage/sessionStorage；保存后立即清空组件内状态；不在控制台/埋点输出。

> 落地时同步更新 [05-页面设计规范](../05-design/03-页面设计规范.md) 与组件库文档。

---

## 9. 核心流程

```
[设置]
用户 → PUT /users/me/llm-credential（JWT）
  → 校验格式/可选 verify（用户 Key 调一次 max_tokens=1）
  → 加密（Fernet）→ upsert user_llm_credentials
  → 返回掩码状态；写 audit_logs

[使用]
用户触发清洗/评估/提取/洞察/报告
  → Agent.invoke(session, user_id)
  → credential_service.get_active(user_id)
      ├─ 有：解密 → LLMClient(api_key=用户Key) → 调用 → 记录 token/成本（估算）
      ├─ 无 + fallback 开：LLMClient(服务端 Key)
      └─ 无 + fallback 关：428 LLM_CREDENTIAL_NOT_CONFIGURED（不调外部 API）
  → 401/无效：标记 invalid → 返回可读错误
```

---

## 10. 配置项（`backend/.env.example`）

```ini
# BYOK：用户自带 LLM API Key
BYOK_ENABLED=true

# 32 字节 base64；缺失时拒绝保存 Key（fail closed，不退化为明文存储）
# 生成：python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# ⚠️ 生产环境：务必通过 Secrets Manager（AWS Secrets Manager / Vault / 平台密钥注入）传入，
#    不得明文写入代码仓库或镜像；本地开发写 .env（.gitignore 已忽略）
# ⚠️ Phase 1 单密钥：密钥丢失已存凭据不可恢复，须做 Secret 备份；
#    密钥轮换能力（MultiFernet）在 Phase 2 实现
CREDENTIAL_ENCRYPTION_KEY=

# 仅开发/CI/E2E：无用户 Key 时回退服务端 DEEPSEEK_API_KEY（生产必须 false）
# 作品集演示账号如需预置体验，建议通过脚本预写加密凭据入库，而非开启此开关
ALLOW_SERVER_KEY_FALLBACK=false

# verify 端点限流（次/分钟/用户）
LLM_CREDENTIAL_VERIFY_PER_MINUTE=5
```

---

## 11. 验收标准（AC）

| 编号 | 验收标准 | 验证方式 |
| --- | --- | --- |
| AC-BK-01 | 新用户未配置 Key 时触发清洗 → 428 `LLM_CREDENTIAL_NOT_CONFIGURED`，且无外部 LLM 请求、无 `llm_calls` 记录 | 集成测试（mock transport 断言调用 0 次） |
| AC-BK-02 | 配置 Key 后触发任一 Agent → 请求头 `Authorization: Bearer <用户Key>`，非服务端 Key | 集成测试（httpx MockTransport 捕获请求头） |
| AC-BK-03 | `GET /users/me/llm-credential` 响应不含完整 Key（正则 `sk-[A-Za-z0-9]{10,}` 不命中），仅 `key_hint`，且 `key_hint` 符合「前5位 + `…` + 后4位」格式 | API 测试 |
| AC-BK-04 | 数据库中 `encrypted_api_key` 不含明文 Key 子串 | 集成测试直接查库断言 |
| AC-BK-05 | 用户 A 无法读取/覆盖用户 B 的凭据（404，无存在性泄露）；admin 亦不可 | 越权测试 |
| AC-BK-06 | 删除 Key 后 AI 操作恢复 428；再次配置后恢复可用 | 集成测试 |
| AC-BK-07 | 无效 Key verify 返回 400；保存的无效 Key 被标记 `invalid`，调用时返回可读错误且不回退服务端 Key；并发任务同时标记时仅触发一次（幂等 `WHERE status != 'invalid'`） | 集成测试 + 并发用例 |
| AC-BK-08 | `ALLOW_SERVER_KEY_FALLBACK=true` 时无 Key 可用服务端 Key；`false` 时绝不回退 | 开关双态测试 |
| AC-BK-09 | `CREDENTIAL_ENCRYPTION_KEY` 缺失时保存失败，数据库无明文写入 | 配置异常测试 |
| AC-BK-10 | verify 超过 5 次/分钟/用户返回 429 | 限流测试 |
| AC-BK-11 | 设置/删除事件写入审计日志，且日志中无 Key 明文 | 审计测试 |
| AC-BK-12 | 现有后端 479 用例、前端 323 用例、E2E 8 条不回归 | 全量门禁 |
| AC-BK-13 | 老用户/种子账号迁移后登录、只读浏览正常 | 迁移 + 冒烟 |
| AC-BK-14 | Phase 1 传入非空 `base_url` 保存时返回 400 `LLM_CREDENTIAL_INVALID`，不发起任何外部 HTTP 请求 | 安全测试（SSRF 防护） |
| AC-BK-15 | 用户 Key 调用的 `llm_calls` 记录 `key_source='user'`，且此类记录不触发 `DAILY_COST_LIMIT` 降级；服务端 Key 调用记录 `key_source='server'` 且仍受降级约束 | 集成测试（双 key_source 降级门禁） |

---

## 12. 测试要求

| 层 | 内容 |
| --- | --- |
| 单元 | 加密/解密往返、掩码生成（前5后4格式）、Key 格式校验（含长度<12拒绝）、解密失败路径、verify 限流、非空 `base_url` 拒绝逻辑 |
| 集成 | 4 个 API 的 CRUD/权限/越权/错误码；Agent 使用用户 Key（MockTransport）；无 Key 428；无效 Key 标记（含并发幂等）；fallback 双态；verify 不写 `llm_calls` 断言 |
| 安全 | 跨用户越权、admin 读取他人、响应/日志无明文、密文落库、限流、审计无敏感值；Phase 1 非空 `base_url` SSRF 防护（AC-BK-14） |
| 成本隔离 | 用户 Key 调用 `key_source='user'` 不触发降级；服务端 Key 调用 `key_source='server'` 仍受 `DAILY_COST_LIMIT` 约束（AC-BK-15） |
| 前端 | 设置 Modal（输入/显示切换/保存/删除/错误提示）、未配置 Banner、按钮禁用与跳转 |
| E2E | 配置 Key → 状态变化 → 删除（用测试替身或 fallback，不调用真实付费 Key；必要时仅在 CI 用 fake transport） |
| 回归 | 5 Agent、成本追踪、降级、SSE、PDF、E2E 全量 |

---

## 13. 迁移与兼容

- 迁移 008 新建 `user_llm_credentials` 表 + 为 `llm_calls`（或等价成本字段）新增 `key_source VARCHAR(10) NOT NULL DEFAULT 'server'`，无业务数据回填；
- 老用户首次访问提示配置 Key；只读浏览正常，不报错；
- 种子管理员同样需自行配置（不再默认使用服务端 Key，除非 fallback 开启）；
- **作品集演示账号**：推荐通过部署脚本预写加密凭据入库（使用 `CREDENTIAL_ENCRYPTION_KEY` 加密一个固定体验 Key 后直接 INSERT），而非开启生产 `ALLOW_SERVER_KEY_FALLBACK`；若部署环境没有真实 Key，可在部署说明中告知访客自行配置；
- 开发/CI/E2E：`ALLOW_SERVER_KEY_FALLBACK=true`，保持现有测试不依赖真实 Key；
- Prompt 测试（`-m prompt`）：仍走服务端 Key 或 CI Secret，不在本需求范围；
- 回滚：`BYOK_ENABLED=false` 即回到现状行为（忽略用户凭据，使用服务端 Key）。

---

## 14. 范围外（Phase 2 候选）

- 多 provider（OpenAI 兼容/Claude/Azure）与自定义模型；
- 团队/组织共享凭据与配额分配；
- 用户 Key 用量看板（DeepSeek 平台已有账单）；
- Key 到期提醒、自动轮换、余额不足预警；
- 管理员为用户重置/代配 Key（安全策略需另行评审）。

---

## 15. 风险与对策

| 风险 | 影响 | 对策 |
| --- | --- | --- |
| `CREDENTIAL_ENCRYPTION_KEY` 丢失 | 已存 Key 无法解密 | 通过 Secrets Manager 管理并备份；错误明确提示用户重新配置；不自动清空；Phase 2 实现 MultiFernet 轮换 |
| `CREDENTIAL_ENCRYPTION_KEY` 泄露 | 攻击者可离线解密数据库密文 | 生产环境通过密钥注入（Secrets Manager/环境注入），不写入代码库或镜像；泄露后需立即轮换（Phase 2 前只能重置所有凭据） |
| `base_url` SSRF 攻击 | 攻击者探测内网或转发请求 | Phase 1 保存时拒绝非空 `base_url`（400）；Phase 2 开放时加 URL 白名单 + 私网 IP 过滤（AC-BK-14） |
| 用户 Key 质量差/欠费 | AI 任务失败 | 保存前 verify；调用失败给出可读提示并标记 invalid |
| 日志/异常泄露 Key | 严重安全事件 | 全链路脱敏；测试正则断言；禁止打印异常原文中的 Key |
| 越权读取 | 严重安全事件 | 仅本人查询；不存在返回 404；安全测试覆盖 |
| verify 被当校验 oracle | 有限滥用 | 登录 + 按用户限流 + 仅能验证自己的 Key |
| 并发任务重复标记 invalid | 副作用重复触发（如通知） | `UPDATE ... WHERE status != 'invalid'`（幂等）；AC-BK-07 并发用例覆盖 |
| 迁移/回滚 | 影响存量用户 | 建表 + 加字段；开关可回退；迁移幂等 |
| 用户 Key 成本累入全局降级阈值 | 用户花自己的钱却触发系统降级 | `llm_calls` 加 `key_source` 字段；降级中间件只聚合 `key_source='server'`（§5 兼容性、AC-BK-15） |

---

## 16. 里程碑与工作量

| 阶段 | 内容 | 人日 |
| --- | --- | --- |
| M1 | 迁移 008 + 模型 + 加密服务 + 4 个 API + 单元/集成测试 | 1.0 |
| M2 | BaseAgent 注入（用户 Key / 428 / invalid / fallback）+ 回归测试 | 0.75 |
| M3 | 前端设置 Modal + 未配置引导 + 前端测试 | 0.75 |
| M4 | E2E/安全测试 + 文档（API/DB/页面/验收清单）+ 口径同步 | 0.5 |
| **合计** | | **≈3 人日** |

---

## 17. 待确认决策（3 项）

> 以下为本文档采用的默认值；确认后冻结，若有变更需回写本文档。

| # | 决策 | 默认（建议） |
| --- | --- | --- |
| D1 | 无 Key 时用户能力 | **只读浏览 + AI 操作拦截引导**（不完全锁死） |
| D2 | 服务端 Key fallback | **仅开发/CI/E2E 开启；生产 false**（不静默用部署者 Key） |
| D3 | provider 范围 | **首批仅 DeepSeek 官方**；表字段预留 `base_url/model`，Phase 2 再扩展 |

---

## 18. 术语与参考

- **BYOK**：Bring Your Own Key，用户自带模型服务商 API Key；
- **key_hint**：仅用于展示的掩码（如 `sk-…a1b2`），不可还原明文；
- **fallback**：无用户 Key 时回退服务端 Key 的行为，仅限开发/CI；
- 现有实现参考：[LLMClient](../../backend/app/core/llm.py#L154-L166)、[BaseAgent.invoke](../../backend/app/agents/base.py#L160-L200)、[Agent 链路调用点](../../backend/app/services/)；
- 相关评审：[T9 成本优化（Phase 1）](../07-review/01-项目现状与待办清单.md) 已落地的提取成本埋点可作为 BYOK 之后成本观测的基础。
