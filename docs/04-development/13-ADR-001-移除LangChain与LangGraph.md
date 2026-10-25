# ADR-001：移除 LangChain 与 LangGraph，改用自研 LLM 客户端与编排器

> **状态**：✅ 已接受
> **决策日期**：2026-10-24
> **决策人**：项目负责人
> **影响范围**：后端 AI 层（Agent / 编排 / 成本 / 测试）、依赖清单、相关设计文档
> **关联**：`12-后端开发计划.md`（D-21）、`backend/requirements.txt`

---

## 1. 背景

项目原技术栈为 **LangChain + LangGraph + langchain-deepseek**（`04-开发方案` §1.3）。截至决策时：

| 事实 | 证据 |
|---|---|
| 框架引用散布在 **19 份文档、166 处** | `grep -c 'langchain\|langgraph' docs/**/*.md` |
| 后端代码**尚无一处真实引用**（全仓仅 `config.py` 一句注释提到） | `backend/app/{agents,services,api,models}` 均为空包 |
| 依赖曾因版本冲突被迫整体升级 | `requirements.txt` L22-29 注释：`langchain==0.1.0 + langchain-core==0.1.10 + langchain-deepseek==0.1.0` 冲突，CI 报 `ResolutionImpossible`，整体升 1.x，并连带把 pydantic 从 2.5 提到 2.14.1 |
| 文档示例在 1.x 下全部失效 | 审查报告：`langchain.agents.AgentExecutor`、`langchain.output_parsers`、`langchain.callbacks` 等旧路径；技术栈文档仍写 LangChain 0.1.0 / LangGraph 0.0.20 |
| 文档存在三份互不兼容的 `BaseAgent` 草案 | Agent 设计（config 版）/ 降级策略（degradation_manager 版）/ 重试机制（retry_config 版），差异本质是"如何把框架对象穿进自己的类" |

**框架在本项目中的真实用武之地**（逐项核对后）：

- LangChain：只用到 `ChatDeepSeek(...).ainvoke()`（HTTP 调用）和 `BaseCallbackHandler.on_llm_end`（读 token 用量）。
- LangGraph：只用到 6 节点 `StateGraph`、1 个条件分支；**未使用** checkpointer / interrupt / 断点续跑（`manual_review` 的恢复机制在文档中本就是"未明确"）。
- **未使用**：LangChain 的 vectorstore、embeddings（项目用 sentence-transformers + pgvector 原生 SQL）、tool-calling（5 个"工具"是纯 Python 函数）、RAG 链、LCEL 组合、多供应商抽象。

也就是说：框架 ≈ 一个 HTTP 客户端 + 一个 if/else 编排，而项目文档本身已要求自研结构化输出、重试、成本、降级、Prompt 资产。

---

## 2. 决策

**移除 LangChain 与 LangGraph 全家桶，改为自研两个薄组件，`BaseAgent` 对外契约保持不变。**

1. 从依赖中删除：`langchain`、`langchain-core`、`langchain-deepseek`、`langgraph`（**不新增任何依赖**，HTTP 客户端复用已锁定的 `httpx==0.26.0`）。
2. 新增 `app/core/llm.py`：`LLMClient`（OpenAI 兼容协议，POST `{DEEPSEEK_BASE_URL}/chat/completions`），负责组 messages、超时、SSE 流式、usage 解析、错误映射、主/降级模型选择。
3. 新增 `app/agents/workflow.py`：显式 async 编排器（6 步 + 1 个条件分支 + 每步落 `tasks` 进度），替代 `StateGraph`。
4. `BaseAgent(config).invoke()` / `AgentConfig` / `AgentResult` / 异常树 / 重试 / 成本 / 结构化输出**全部保持`02-Agent详细设计` §1.2 的契约**，Service 与 API 层零改动。

---

## 3. 理由

| # | 理由 |
|---|---|
| R1 | **收益/成本倒挂**：框架提供的能力 90% 未被使用，而项目自己的设计已经把成本、重试、降级、结构化输出、Prompt 资产全部自研——多一层框架只是多一层适配与不一致（三份 BaseAgent 草案即证据）。 |
| R2 | **适配成本已实际发生**：一次被迫的 1.x 升级改造 + 全仓文档示例失效 + `ChatPromptTemplate` 花括号转义问题（审查报告 P0-12，文档专门要求 `{}`→`{{ }}`）。 |
| R3 | **可靠性反而更低**：成本统计依赖同步 `on_llm_end` + `asyncio.create_task` 落库，文档自述存在丢写风险；而直读 HTTP 响应 usage 无此问题。 |
| R4 | **测试更脆弱**：单测必须 patch "被测模块里引用的 `ChatDeepSeek`"，patch 库本身不生效（`06-testing/01` §7.1 专门警告）。自研客户端可直接注入 fake。 |
| R5 | **零业务代码时切换成本最低**：当前后端 Agent 代码为 0 行，改造成本仅"依赖 + 文档 + 250 行新代码"；若 5 个 Agent 写完后再换，成本约 10 倍。 |
| R6 | **`BaseAgent` 契约与框架解耦**：契约属于项目自己的抽象，换实现不影响 Service/API，风险可控。 |

---

## 4. 备选方案

| 方案 | 内容 | 结论 |
|---|---|---|
| A. 全去（**采纳**） | 自研 LLM 客户端 + 自研编排，0 框架依赖 | ✅ 采纳 |
| B. 去 LangChain、留 LangGraph | 仅用 StateGraph 编排，节点写纯函数 | ❌ 保留 1 个依赖仍需 `langchain-core`，而编排只需 ~150 行；除非确定做断点续跑 |
| C. 维持现状 | 把框架当薄客户端 + 状态图 | ❌ 继续承担版本锁定与适配成本，问题不消失 |
| D. 1 天对比 Spike | 同需求两版实现后实测 | ❌ 决策依据已充分（0 代码、0 真实依赖），Spike 只增加 1 天 |

---

## 5. 迁移映射

| 原实现 | 新实现 | 说明 |
|---|---|---|
| `ChatDeepSeek(model=…).ainvoke(messages)` | `LLMClient.chat(messages)` | 返回 `LLMResponse{content, usage(input/output/total), model, latency_ms}` |
| `ChatDeepSeek(...).astream(...)` | `LLMClient.stream(messages)` | httpx 流式读取 SSE，MVP 不做前端流式（D-07） |
| `BaseCallbackHandler.on_llm_end` 取 token | `LLMResponse.usage` | 直接由响应体读取，`CostTracker.track()` 只接收 usage |
| `ChatPromptTemplate` + 花括号转义 | messages 列表 + `system.txt` 原文 | 不再需要转义，`examples.json` 以消息形式注入 |
| `StateGraph.add_node/add_conditional_edges` | `async def run(state)` + `if` 分支 | 每步完成后写 `tasks.progress/current_step`，失败可 `retry` |
| `PydanticOutputParser` | `parse_with_repair` + Pydantic 校验 | 文档既定方案，保持不变 |
| `create_react_agent` / `AgentExecutor` | 不实现 | 当前 Agent 是"单次调用 + JSON 输出"，无 ReAct 循环 |

---

## 6. 自研边界（防止变成"重写框架"）

**只允许实现 4 件事**：①LLM 调用（含流式）②结构化输出兜底 ③重试/超时 ④编排与进度落库。

**禁止清单**（出现即视为超出边界，需评审）：

- 通用 provider 注册表 / 插件体系 / 多模态抽象；
- 链式 DSL、Runnable 协议、回调总线；
- 可视化画布、时间旅行、图编译缓存；
- 为"未来可能的功能"预留抽象（YAGNI）。

**硬指标**：`app/core/llm.py` + `app/agents/workflow.py` 合计 **≤ 300 行**（不含测试）；必须 100% 类型注解 + 单测覆盖超时/错误映射/usage 解析/分支。

---

## 7. 重新评估触发条件

出现以下**任一确定需求**时，再评估引入 LangGraph（或等价持久化编排）：

1. 人工审核需要**暂停数小时/数天后恢复**（durable execution / checkpoint）；
2. 需要 **ReAct 多轮工具调用**（LLM 自主决定调用外部工具并循环）；
3. 需要**多模态**（图片/语音）或多供应商灰度路由；
4. 工作流复杂到自研编排超过 300 行且分支难以维护。

**回滚成本**：因为 `BaseAgent` 契约不变，替换 `workflow.py` 内部实现即可，Service/API/DB 不受影响（预估 2-3 人日）。

---

## 8. 影响与待办

### 8.1 依赖

`backend/requirements.txt` 删除 4 行（`langchain`/`langchain-core`/`langchain-deepseek`/`langgraph`），无新增依赖。

### 8.2 代码

| 文件 | 动作 |
|---|---|
| `app/core/llm.py` | 新增（LLMClient） |
| `app/agents/workflow.py` | 新增（编排器），原名保留 |
| `app/agents/base.py` | 按原契约实现，内部用 LLMClient |
| `app/core/cost_tracker.py` | `track()` 输入改为 `LLMResponse.usage` |
| `app/core/config.py` | 仅更新文件头注释（模型 id 仍读 `DEFAULT_LLM_MODEL`） |
| `backend/README.md` | 「约定-模型」一节改为 LLMClient |

### 8.3 文档回写清单（回写前，以下文档中框架相关示例以本 ADR 为准）

| # | 文档 | 需处理的内容 |
|---|---|---|
| 1 | `00-AI应用开发基调.md` | L38-49 导入示例、L280 口径、L671-700 工作流、L737-741/L801-820 选型说明 |
| 2 | `01-requirements/01-产品概述.md` | L439-440 技术选型表述 |
| 3 | `01-requirements/00-需求讨论记录.md` | L394-406 为历史讨论记录，保留并加"已被 ADR-001 取代"注记 |
| 4 | `02-design/01-Prompt工程规范.md` | L49、L363-421（ChatPromptTemplate 与转义）、L746-754 |
| 5 | `02-design/02-Prompt版本管理方案.md` | L425-436 示例 |
| 6 | `03-architecture/01-系统架构.md` | L46 架构图、L105-107 技术栈、L387-412 工作流、L555 引用 |
| 7 | `03-architecture/02-Agent详细设计.md` | L66/L151-153/L174/L245/L281 接口与注释、L923、L1339-1499 工作流 |
| 8 | `04-development/01-开发规范.md` | L326 注释、L357-420 BaseAgent 示例 |
| 9 | `04-development/02-技术栈详细说明.md` | L42、L61-63 版本表、L812-926 示例、L1248-1273 选型理由 |
| 10 | `04-development/03-成本管理.md` | L477-533 LangChain 回调、L804-809 示例 |
| 11 | `04-development/04-开发方案.md` | L43 技术栈、L450-453 依赖、L596-652 POC1、L772-826 POC3、L845-891 POC4、L1573 风险、L1684-1686 |
| 12 | `06-testing/00-测试策略总览.md`、`01-后端单元测试规范.md`、`03-Prompt测试规范.md` | mock `ChatDeepSeek` 的示例改为注入 fake `LLMClient` |
| 13 | `07-review/00-文档审查报告.md` | 历史审查报告，保留并加"部分结论已被 ADR-001 取代"注记 |
| 14 | `README.md` | L27 技术栈、L382 致谢 |

### 8.4 开发计划任务变更

| 任务 | 变更 |
|---|---|
| B-101 | POC1 改为「LLM 协议验证（无框架）：调用 + JSON + usage」 |
| B-103 | POC3 改为「自研编排器原型：6 步 + 条件分支 + 失败不中断」 |
| B-104 | 成本 POC 改为「响应 usage 直读 → 成本计算」 |
| **B-200（新增）** | 实现 `app/core/llm.py` LLMClient（含流式/超时/错误映射/usage）+ 单测 |
| B-310 | BaseAgent 内部改为依赖 `LLMClient` |
| B-604 | 编排器 `workflow.py`（自研），不再用 LangGraph |
| B-704 | 文档回写按 §8.3 清单执行 |

---

## 9. 后果与风险

**正面**：依赖更少、升级负担消失、调试链路变短（一个 HTTP 调用 = 一次函数调用）、mock 更容易、文档示例可直接运行。

**负面/风险**：

| 风险 | 对策 |
|---|---|
| 自研层逐渐膨胀成"重写框架" | §6 禁止清单 + 300 行上限 + 代码评审 |
| 未来 HITL 断点续跑需求出现 | §7 触发条件，届时替换 `workflow.py` 实现即可；或用 `tasks` 表 + Celery 状态机过渡 |
| 文档长期与代码不一致 | §8.3 回写清单纳入 B-704，按阶段回写；B-002 决策记录同步 |
| 流式实现细节踩坑（SSE 分片） | POC1 验证；MVP 前端不做流式（D-07），先保证非流式稳定 |

---

## 10. 参考

- `docs/04-development/12-后端开发计划.md` §4.4（D-21）
- `docs/04-development/04-开发方案.md` §1.3/§4（原 POC 设计）
- `docs/03-architecture/02-Agent详细设计.md` §1.2（BaseAgent 契约，继续有效）
- `docs/07-review/00-文档审查报告.md`（框架相关导入路径问题、P0-12 转义问题）
