# AI Insight Hub Prompt 工程规范

> **文档版本**：v1.0  
> **创建日期**：2026年10月23日  
> **适用范围**：所有 AI Agent 开发  
> **核心理念**：Prompt is Code, Version is Everything

---

## 📋 目录

1. [Prompt 工程概述](#1-prompt-工程概述)
2. [目录结构规范](#2-目录结构规范)
3. [Prompt 模板规范](#3-prompt-模板规范)
4. [版本管理](#4-版本管理)
5. [测试与评估](#5-测试与评估)
6. [最佳实践](#6-最佳实践)
7. [常见问题](#7-常见问题)

---

## 1. Prompt 工程概述

### 1.1 为什么 Prompt 需要工程化？

**传统做法（❌）**：
```python
# Prompt 硬编码在代码中
def clean_data(data):
    prompt = f"Clean this data: {data}"
    result = llm.generate(prompt)
    return result
```

**问题**：
- ❌ Prompt 散落在代码中，难以维护
- ❌ 无版本管理，不知道哪个版本效果好
- ❌ 无法 A/B 测试
- ❌ 改动需要改代码，风险大

**工程化做法（✅）**：
```python
# Prompt 独立管理
class DataCleaningAgent:
    PROMPT_DIR = Path("prompts/cleaning")
    
    def _load_prompt(self):
        system = (self.PROMPT_DIR / "system.txt").read_text()
        return PromptTemplate(template=system)
    
    def clean(self, data):
        prompt = self._load_prompt()
        result = llm.generate(prompt.format(data=data))
        return result
```

**优势**：
- ✅ Prompt 集中管理
- ✅ 支持版本控制
- ✅ 可以 A/B 测试
- ✅ 改 Prompt 不改代码

---

### 1.2 核心原则

1. **Prompt 是资产**：像代码一样管理
2. **可测试**：每个 Prompt 都有测试用例
3. **可追溯**：知道每个版本的效果
4. **可迭代**：基于数据持续优化
5. **可复用**：模块化，减少重复

---

## 2. 目录结构规范

### 2.1 标准目录结构

```
backend/
└── app/
    └── prompts/                      # Prompt 资产库
        ├── README.md                 # 使用说明
        ├── _shared/                  # 共享组件
        │   ├── output_format.txt     # 通用输出格式
        │   ├── rules.txt             # 通用规则
        │   └── examples.json         # 通用示例
        │
        ├── cleaning/                 # 数据清洗 Agent
        │   ├── README.md             # Agent 说明
        │   ├── system.txt            # 系统提示词（主）
        │   ├── user_template.txt     # 用户提示词模板
        │   ├── examples.json         # Few-shot 示例
        │   ├── version.txt           # 版本号
        │   └── tests/                # Prompt 测试
        │       └── test_cases.json
        │
        ├── evaluation/               # 质量评估 Agent
        │   ├── README.md
        │   ├── system.txt
        │   ├── dimensions/           # 评估维度（共 5 个，与 03-architecture/02-Agent详细设计.md 一致）
        │   │   ├── accuracy.txt      # 准确性评估
        │   │   ├── completeness.txt  # 完整性评估
        │   │   ├── tone.txt          # 语气礼貌度评估
        │   │   ├── compliance.txt    # 合规性评估
        │   │   └── hallucination.txt # 幻觉检测
        │   ├── examples.json
        │   └── version.txt
        │
        ├── extraction/               # 知识提取 Agent
        │   ├── README.md
        │   ├── system.txt
        │   ├── examples.json
        │   └── version.txt
        │
        ├── insight/                  # 洞察分析 Agent
        │   ├── README.md
        │   ├── system.txt
        │   ├── examples.json
        │   └── version.txt
        │
        └── report/                   # 报告生成 Agent
            ├── README.md
            ├── system.txt
            ├── templates/            # 报告模板（4 类，命名与 02-Agent详细设计.md 一致）
            │   ├── quality_report.txt        # 质量报告
            │   ├── knowledge_report.txt      # 知识库报告
            │   ├── insight_report.txt        # 洞察报告
            │   └── comprehensive_report.txt  # 综合报告
            └── version.txt
```

> **目录与命名对齐**：评估维度固定 5 个（`accuracy / completeness / tone / compliance / hallucination`）；报告模板固定 4 个，文件名为 `quality_report.txt / knowledge_report.txt / insight_report.txt / comprehensive_report.txt`，以 `docs/03-architecture/02-Agent详细设计.md` 为准。

---

### 2.2 文件命名规范

| 文件名 | 用途 | 必需 |
|--------|------|------|
| `README.md` | Agent 说明文档 | ✅ |
| `system.txt` | 系统提示词（角色+任务） | ✅ |
| `user_template.txt` | 用户提示词模板 | 可选 |
| `examples.json` | Few-shot 示例 | 推荐 |
| `version.txt` | 版本号和更新日志 | ✅ |
| `tests/` | 测试用例目录 | ✅ |

---

## 3. Prompt 模板规范

### 3.1 System Prompt 结构

**标准模板**：

```text
# 角色定义
你是一个[角色描述]。

# 任务
[明确的任务描述]

# 输入格式
[输入的数据结构和格式]

# 输出格式
[期望的输出格式，最好是结构化的]

# 规则
[必须遵守的规则，用编号列表]

# 示例（可选）
[Few-shot 示例，展示期望的输入输出]

# 注意事项
[特殊注意事项或边界情况]
```

---

### 3.2 实际示例：数据清洗 Agent

**prompts/cleaning/system.txt**：

````text
# 角色定义
你是一个专业的客服对话数据清洗专家，擅长从非结构化数据中提取和标准化信息。

# 任务
从原始的客服对话数据中提取关键信息，并转换为标准化的 JSON 格式。

# 输入格式
你会收到以下任意格式的数据：
1. CSV 格式的文本
2. 纯文本对话记录
3. JSON 片段（可能格式不规范）

示例输入：
```
时间: 2025-01-15 10:30
客户: 你好，我想咨询一下 iPhone 14 的价格
客服: 您好！iPhone 14 目前的价格是 5999 元起，有多种配置可选。
```

# 输出格式
必须输出标准的 JSON 对象，包含以下字段（**字段注释只写在下方表格里，不要写进 JSON**，否则 JSON 非法）：

```json
{
  "dialogue_id": "string",
  "timestamp": "string",
  "user_message": "string",
  "ai_response": "string",
  "metadata": {
    "source": "string|null",
    "session_id": "string|null"
  },
  "quality_score": 100,
  "issues": ["string"],
  "error": null
}
```

字段说明：

| 字段 | 类型 | 说明 |
|------|------|------|
| `dialogue_id` | string | 唯一标识符，使用 UUID v4 |
| `timestamp` | string | ISO 8601 格式，如 `"2025-01-15T10:30:00Z"`；原始数据无时间时使用当前时间 |
| `user_message` | string | 用户的消息内容 |
| `ai_response` | string | AI/客服的回复内容 |
| `metadata` | object | `source` 为数据来源（可为 null）；`session_id` 为会话 ID（可为 null） |
| `quality_score` | number | 数据质量评分，0-100（算法见下方规则 4） |
| `issues` | string[] | 发现的问题列表，无问题时为 `[]` |
| `error` | string\|null | **仅在输入完全无法解析时非 null**，值为失败原因；正常解析时必须为 `null` |

# 规则
1. **所有字段必须存在**，缺失的用 null 或空数组
2. **timestamp 必须是 ISO 8601 格式**，如果原始数据没有时间，使用当前时间
3. **dialogue_id 必须是唯一的 UUID v4**
4. **quality_score 计算规则**（基准分 100，逐项扣分，下限 0；示例见 examples.json）：
   - 基准分：100（完整对话 = 有用户消息且有回复、字段齐全、内容规范）
   - 缺少时间戳：-10 分（timestamp 字段仍按当前时间补齐，同时记入 issues）
   - 消息内容过短（< 5 字）：-20 分
   - 包含乱码或无效字符：-30 分
   - 对话不完整（缺少用户消息或回复）：-40 分
   - 输入完全无法解析（`error` 字段非 null）：`quality_score` 取 0-30 的估计值（无法可靠评分）
5. **检测并标注以下问题**：
   - "missing_timestamp": 缺少时间戳
   - "short_message": 消息过短
   - "invalid_chars": 包含无效字符
   - "incomplete_dialogue": 对话不完整
   - "duplicate_suspected": 疑似重复
6. **去重规则**：
   - 完全相同的对话：只保留一条
   - 相似度 > 95% 的对话：标记为 "duplicate_suspected"
7. **数据清洗**：
   - 移除前后空白字符
   - 规范化标点符号（全角转半角）
   - 移除 HTML 标签
   - 处理转义字符

# 注意事项
1. 如果输入数据完全无法解析，返回 error 字段说明原因
2. 尽可能提取信息，即使格式不标准
3. 不要编造不存在的信息
4. 保持原始内容的语义，不要改写

# 示例
Few-shot 示例由 examples.json 提供，调用时注入 2-3 条（见 3.3 节 `_load_examples()` 实现）
````

---

**prompts/cleaning/examples.json**：

```json
{
  "version": "1.0.0",
  "examples": [
    {
      "name": "标准 CSV 格式",
      "input": "时间: 2025-01-15 10:30\n客户: 你好，我想咨询一下 iPhone 14 的价格\n客服: 您好！iPhone 14 目前的价格是 5999 元起。",
      "expected_output": {
        "dialogue_id": "550e8400-e29b-41d4-a716-446655440000",
        "timestamp": "2025-01-15T10:30:00Z",
        "user_message": "你好，我想咨询一下 iPhone 14 的价格",
        "ai_response": "您好！iPhone 14 目前的价格是 5999 元起。",
        "metadata": {
          "source": null,
          "session_id": null
        },
        "quality_score": 100,
        "issues": []
      }
    },
    {
      "name": "缺少时间戳",
      "input": "客户: 退货需要多久？\n客服: 7 天内可以无理由退货。",
      "expected_output": {
        "dialogue_id": "550e8400-e29b-41d4-a716-446655440001",
        "timestamp": "2025-01-15T00:00:00Z",
        "user_message": "退货需要多久？",
        "ai_response": "7 天内可以无理由退货。",
        "metadata": {
          "source": null,
          "session_id": null
        },
        "quality_score": 90,
        "issues": ["missing_timestamp"]
      }
    },
    {
      "name": "消息过短",
      "input": "客户: 好\n客服: 嗯",
      "expected_output": {
        "dialogue_id": "550e8400-e29b-41d4-a716-446655440002",
        "timestamp": "2025-01-15T00:00:00Z",
        "user_message": "好",
        "ai_response": "嗯",
        "metadata": {
          "source": null,
          "session_id": null
        },
        "quality_score": 70,
        "issues": ["missing_timestamp", "short_message"]
      }
    }
  ]
}
```

---

### 3.3 User Prompt 模板

**prompts/cleaning/user_template.txt**：

````text
请清洗以下客服对话数据：

```
{raw_data}
```

数据源信息：
- 数据源 ID: {datasource_id}
- 数据类型: {data_type}
- 预期记录数: {expected_count}

# Few-shot 示例（由 examples.json 注入，统一取 2-3 条）
{few_shot_examples}

请严格按照系统提示词中的规则和格式输出 JSON。
````

**Python 中使用**：

```python
import json
from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate
from langchain_deepseek import ChatDeepSeek

from app.core.config import settings

class DataCleaningAgent:
    PROMPT_DIR = Path(__file__).parent.parent / "prompts" / "cleaning"

    def __init__(self):
        self.llm = ChatDeepSeek(
            model=settings.DEFAULT_LLM_MODEL,          # 模型 id 不写死，统一走配置
            temperature=settings.DEFAULT_TEMPERATURE,  # 结构化输出默认 0
        )

    def _load_prompts(self):
        system = (self.PROMPT_DIR / "system.txt").read_text(encoding="utf-8")
        user_template = (self.PROMPT_DIR / "user_template.txt").read_text(encoding="utf-8")

        # system.txt 内含 JSON 示例的 {}，必须先转义为 {{ }} 再交给 ChatPromptTemplate，
        # 否则 LangChain 会把 {"dialogue_id": ...} 当作模板变量解析并抛错。
        system_escaped = system.replace("{", "{{").replace("}", "}}")

        return ChatPromptTemplate.from_messages([
            ("system", system_escaped),
            ("human", user_template),
        ])

    def _load_examples(self, limit: int = 3) -> str:
        """加载 Few-shot 示例（本项目统一 2-3 条；字段名固定 input/expected_output）"""
        data = json.loads(
            (self.PROMPT_DIR / "examples.json").read_text(encoding="utf-8")
        )
        chunks = []
        for example in data["examples"][:limit]:
            chunks.append(
                f"示例输入：\n{example['input']}\n"
                f"示例输出：\n{json.dumps(example['expected_output'], ensure_ascii=False)}"
            )
        return "\n\n".join(chunks)

    def clean(self, raw_data: str, datasource_id: str, **kwargs):
        prompt = self._load_prompts()

        messages = prompt.format_messages(
            raw_data=raw_data,
            datasource_id=datasource_id,
            data_type=kwargs.get("data_type", "unknown"),
            expected_count=kwargs.get("expected_count", "unknown"),
            few_shot_examples=self._load_examples(),  # 真正注入 Few-shot
        )

        result = self.llm.invoke(messages)
        return result
```

> **说明**：
> 1. `_load_examples()` 把 `examples.json` 真正拼进 Human 消息；只在 system.txt 里写「见 examples.json」而加载时不注入，Few-shot 不会生效。
> 2. `examples.json` 中每条示例固定使用 `input` / `expected_output` 两个字段，便于代码通用读取；示例条数统一 2-3 条。
> 3. 若改用 `messages` 列表直接调用（不经过 `ChatPromptTemplate`），则**不要转义**花括号——转义只针对模板解析路径。

---

## 4. 版本管理

### 4.1 版本号规范

**格式**：`v{major}.{minor}.{patch}`

- **Major**：重大变更（不兼容）
- **Minor**：新增功能（兼容）
- **Patch**：Bug 修复（兼容）

**示例**：
```
v1.0.0 - 初始版本
v1.1.0 - 添加去重功能
v1.1.1 - 修复时间戳解析 Bug
v2.0.0 - 输出格式重大调整
```

---

### 4.2 version.txt 格式

**prompts/cleaning/version.txt**：

```
CURRENT_VERSION: v1.2.0
LAST_UPDATED: 2025-01-15
STATUS: production

---

## 更新日志

### v1.2.0 (2025-01-15)
- 添加相似度去重功能
- 优化质量评分算法
- 测试准确率：96.5%
- Token 使用：平均 450/条

### v1.1.0 (2025-01-10)
- 添加 HTML 标签清理
- 改进时间戳解析
- 测试准确率：95.2%

### v1.0.0 (2025-01-01)
- 初始版本
- 基础数据清洗功能
- 测试准确率：92.8%

---

## 性能指标（v1.2.0）

准确率: 96.5%
召回率: 94.2%
F1 Score: 95.3%
平均耗时: 1.2 秒/条
Token 消耗: 450 tokens/条
成本: 按实际模型单价重算（= 单价 × 450 tokens，DeepSeek 实际单价以官方页面为准，本文档不写死金额）

---

## 测试覆盖

测试用例数: 50（每维度 ≥10 条，合计 ≥50 条）
通过率: 98%
失败用例: 1 (边界情况)

---

## 已知问题

- [ ] 繁体中文支持不完善
- [ ] 极长文本（>5000字）处理慢

---

## 下一步计划

- [ ] 支持多轮对话
- [ ] 添加情感标注
- [ ] 优化长文本处理
```

---

### 4.3 Git 管理

**Prompt 变更也要 Commit**：

```bash
# ✅ 正确
git add prompts/cleaning/
git commit -m "feat(prompt): improve cleaning agent deduplication (v1.2.0)"

# 提交信息包含：
# 1. 类型（feat/fix/perf）
# 2. 范围（prompt）
# 3. 描述
# 4. 版本号
```

**分支 / 合并 / 回滚与 Git 的对应约定**：

| 环节 | Git 操作 | 对应 DB 状态（见 `02-Prompt版本管理方案.md`） |
|------|----------|------------------------------------------|
| 起草 | `git switch -c prompt/cleaning-v1.3.0`（一个候选版本一个分支） | `status = 'draft'` |
| 评审 | PR + `git diff prompts/cleaning/`（system.txt / user_template.txt / examples.json 均可 diff） | `status = 'testing'` |
| 发布 | `git merge --no-ff` 合入 `main`，打 tag `prompt-cleaning-v1.3.0` | `status = 'active'`、`is_default = TRUE` |
| 回滚 | `git revert <merge_commit>`（节点级回滚，保留历史） | 由 `rollback_to_version()` 把旧版本重新置为 `is_default`，并写 `version_rollback_logs` |

> **单一真相源约定**：Prompt 文本以数据库 `prompt_versions` 表为准，`prompts/**/*.txt` 为导出/备份产物；
> 两者由 `PromptVersionService.export_to_files()` / `import_from_files()` 双向同步，禁止只改文件不改库。
> 详见 `02-Prompt版本管理方案.md` 第 3 节。

---

## 5. 测试与评估

### 5.1 测试用例结构

**用例数量口径**：每个维度 ≥10 条，合计 ≥50 条（覆盖：正常情况 / 缺失数据 / 异常情况 / 边界情况）。下文 4 条为格式示例。

**backend/app/prompts/cleaning/tests/test_cases.json**：

```json
{
  "test_suite": "data_cleaning_agent",
  "version": "v1.2.0",
  "created_at": "2025-01-15",
  "test_cases": [
    {
      "id": "TC001",
      "name": "标准格式对话",
      "category": "正常情况",
      "input": {
        "raw_data": "时间: 2025-01-15 10:30\n客户: iPhone 14 多少钱？\n客服: 5999 元起。",
        "datasource_id": "test-001"
      },
      "expected": {
        "success": true,
        "quality_score_min": 90,
        "required_fields": ["dialogue_id", "timestamp", "user_message", "ai_response"],
        "issues": []
      }
    },
    {
      "id": "TC002",
      "name": "缺少时间戳",
      "category": "缺失数据",
      "input": {
        "raw_data": "客户: 可以退货吗？\n客服: 7 天内可以。",
        "datasource_id": "test-002"
      },
      "expected": {
        "success": true,
        "quality_score_min": 80,
        "quality_score_max": 95,
        "issues": ["missing_timestamp"]
      }
    },
    {
      "id": "TC003",
      "name": "完全无效数据",
      "category": "异常情况",
      "input": {
        "raw_data": "@@##$$%%",
        "datasource_id": "test-003"
      },
      "expected": {
        "success": false,
        "error": true,
        "quality_score_max": 30
      }
    },
    {
      "id": "TC004",
      "name": "重复对话",
      "category": "边界情况",
      "input": {
        "raw_data": "客户: 你好\n客服: 您好\n\n客户: 你好\n客服: 您好",
        "datasource_id": "test-004"
      },
      "expected": {
        "success": true,
        "issues_contains": "duplicate_suspected"
      }
    }
  ]
}
```

---

### 5.2 自动化测试脚本

**backend/tests/prompts/test_cleaning_agent.py**：

```python
import json
from pathlib import Path

import pytest

from app.agents.cleaning_agent import DataCleaningAgent

# backend/tests/prompts/test_cleaning_agent.py → parents[2] 即 backend/
TEST_CASES_PATH = (
    Path(__file__).resolve().parents[2]
    / "app" / "prompts" / "cleaning" / "tests" / "test_cases.json"
)

class TestCleaningAgentPrompt:
    """数据清洗 Agent Prompt 测试（用例口径：每维度 ≥10 条，合计 ≥50 条）"""

    @pytest.fixture
    def agent(self):
        return DataCleaningAgent()

    @pytest.fixture
    def test_cases(self):
        """加载测试用例"""
        return json.loads(TEST_CASES_PATH.read_text(encoding="utf-8"))

    def test_all_cases(self, agent, test_cases):
        """运行所有测试用例"""
        results = []

        for case in test_cases["test_cases"]:
            result = self._run_test_case(agent, case)
            results.append(result)

            if result["passed"]:
                print(f"✅ {case['id']}: {case['name']}")
            else:
                print(f"❌ {case['id']}: {case['name']}")
                print(f"   原因: {result['reason']}")

        # 计算通过率
        pass_rate = sum(r["passed"] for r in results) / len(results)
        assert pass_rate >= 0.95, f"通过率 {pass_rate:.1%} 低于 95%"

    def _run_test_case(self, agent, case):
        """运行单个测试用例"""
        try:
            # 1. 执行：clean() 返回的是 LLM 文本，必须先解析成 JSON 再断言
            raw_result = agent.clean(**case["input"])
            result = json.loads(raw_result) if isinstance(raw_result, str) else raw_result

            expected = case["expected"]

            # 2. 成功 / 失败（无法解析时必须返回非 null 的 error）
            if expected.get("success") is False:
                if result.get("error") is not None:
                    return {"passed": True}
                return {"passed": False, "reason": "期望失败但未返回 error 字段"}

            # 3. 必需字段
            for field in expected.get("required_fields", []):
                if field not in result:
                    return {"passed": False, "reason": f"缺少字段 {field}"}

            # 4. 质量分区间（下限 + 上限）
            score = result.get("quality_score")
            if "quality_score_min" in expected and score < expected["quality_score_min"]:
                return {
                    "passed": False,
                    "reason": f"质量分 {score} 低于 {expected['quality_score_min']}",
                }
            if "quality_score_max" in expected and score > expected["quality_score_max"]:
                return {
                    "passed": False,
                    "reason": f"质量分 {score} 高于 {expected['quality_score_max']}",
                }

            # 5. 问题列表（全等 / 包含两种断言）
            if "issues" in expected and result.get("issues") != expected["issues"]:
                return {
                    "passed": False,
                    "reason": f"问题列表不匹配: {result.get('issues')} != {expected['issues']}",
                }
            if "issues_contains" in expected:
                if expected["issues_contains"] not in result.get("issues", []):
                    return {
                        "passed": False,
                        "reason": f"问题列表缺少 {expected['issues_contains']}",
                    }

            return {"passed": True}

        except json.JSONDecodeError as exc:
            return {"passed": False, "reason": f"输出不是合法 JSON: {exc}"}
        except Exception as exc:
            return {"passed": False, "reason": str(exc)}
```

**运行测试**：

```bash
# 在 backend/ 目录下执行

# 运行 Prompt 测试
pytest tests/prompts/test_cleaning_agent.py -v

# 查看覆盖率
pytest tests/prompts/ --cov=app/prompts --cov-report=html
```

---

### 5.3 A/B 测试

**目的**：对比不同 Prompt 版本的效果

```python
import json
import random
import time
from datetime import datetime

import numpy as np
from langchain_deepseek import ChatDeepSeek

from app.core.config import settings

class ABTestingAgent:
    """支持 A/B 测试的 Agent"""
    
    def __init__(self):
        self.llm = ChatDeepSeek(
            model=settings.DEFAULT_LLM_MODEL,          # 模型 id 统一走配置
            temperature=settings.DEFAULT_TEMPERATURE,
        )
        self.variants = {
            "A": self._load_prompt_version("v1.1.0"),
            "B": self._load_prompt_version("v1.2.0")
        }
        self.results = {"A": [], "B": []}
    
    def _load_prompt_version(self, version: str):
        """按版本加载 Prompt（生产实现见 02-Prompt版本管理方案.md 的 VersionService）"""
        raise NotImplementedError

    @staticmethod
    def _mean(values):
        """空列表返回 0.0，避免 np.mean([]) 产生 nan"""
        return float(np.mean(values)) if values else 0.0
    
    def clean(self, data, test_group=None):
        """执行清洗并记录结果"""
        # 分组（50/50）
        if test_group is None:
            test_group = "A" if random.random() < 0.5 else "B"
        
        # 执行
        start_time = time.time()
        prompt = self.variants[test_group]
        raw = self.llm.invoke(prompt.format(data=data))
        duration = time.time() - start_time
        # LLM 返回的是消息对象，取 content 后再解析 JSON
        result = json.loads(raw.content if hasattr(raw, "content") else raw)
        
        # 记录
        self.results[test_group].append({
            "timestamp": datetime.now(),
            "duration": duration,
            "quality_score": result.get("quality_score"),
            "issues_count": len(result.get("issues", []))
        })
        
        return result
    
    def get_ab_test_report(self):
        """生成 A/B 测试报告"""
        report = {}
        
        for variant in ["A", "B"]:
            data = self.results[variant]
            report[variant] = {
                "count": len(data),
                "avg_duration": self._mean([r["duration"] for r in data]),
                "avg_quality": self._mean([r["quality_score"] for r in data]),
                "avg_issues": self._mean([r["issues_count"] for r in data])
            }
        
        # 统计显著性检验
        from scipy import stats
        quality_a = [r["quality_score"] for r in self.results["A"]]
        quality_b = [r["quality_score"] for r in self.results["B"]]
        t_stat, p_value = stats.ttest_ind(quality_a, quality_b)
        
        report["significance"] = {
            "t_statistic": t_stat,
            "p_value": p_value,
            "is_significant": p_value < 0.05
        }
        
        return report
```

---

## 6. 最佳实践

### 6.1 Prompt 编写技巧

#### ✅ 清晰的角色定义

```text
# ❌ 模糊
你是一个 AI 助手。

# ✅ 具体
你是一个专业的客服对话数据清洗专家，拥有 5 年的数据处理经验，
擅长从非结构化文本中提取关键信息并标准化。
```

#### ✅ 明确的输出格式

```text
# ❌ 模糊
请输出结果。

# ✅ 具体
输出必须是标准 JSON 格式：
{
  "field1": "类型说明",
  "field2": "类型说明"
}
```

#### ✅ 编号的规则列表

```text
# ❌ 段落描述
你需要检查数据的完整性和准确性，如果发现问题要标注，
同时要注意时间格式要统一...

# ✅ 编号列表
规则：
1. 检查数据完整性，缺失字段用 null
2. 检查数据准确性，标注发现的问题
3. 统一时间格式为 ISO 8601
4. ...
```

#### ✅ Few-shot 示例

```text
# ❌ 没有示例
请提取用户诉求。

# ✅ 有示例
示例 1:
输入: "这个产品太贵了"
输出: {"type": "投诉", "category": "价格", "sentiment": "负面"}

示例 2:
输入: "什么时候发货？"
输出: {"type": "咨询", "category": "物流", "sentiment": "中性"}

现在请处理以下输入：
...
```

---

### 6.2 性能优化

#### 减少 Token 消耗

```text
# ❌ 冗长
你是一个非常专业的、经验丰富的、技能卓越的数据清洗专家，
你拥有多年的实战经验，能够处理各种复杂的数据情况...

# ✅ 简洁
你是一个专业的数据清洗专家。
```

#### 避免重复

```text
# ❌ 每次都发送全量 Few-shot
系统提示词 + examples.json 中全部示例（token 随示例数线性增长）

# ✅ 按需注入
系统提示词: "参考 examples.json 中的示例"
实际调用时注入 2-3 个相关示例 (300 tokens)
```

---

### 6.3 常见陷阱

#### 陷阱 1：过度具体

```text
# ❌ 太具体（无法泛化）
如果用户问"iPhone 14 多少钱"，回答"5999 元"

# ✅ 泛化
如果用户咨询产品价格，只做字段提取与内容规范化，不要改写、补充或推断价格
```

> 说明：价格查询需要知识库检索能力，属于**评估 / 洞察 Agent** 的职责；清洗 Agent 不挂检索工具，因此清洗类 Prompt 中不出现「从知识库查找价格」这类指导。

#### 陷阱 2：假设模型知道的

```text
# ❌ 假设模型知道当前日期
请分析今天的数据。

# ✅ 明确传入
请分析 {current_date} 的数据。
```

> `{current_date}` 是**模板变量，必须由调用方注入**，例如
> `prompt.format(current_date=datetime.now().date().isoformat())`；
> 不要指望 LLM 自己知道「今天」。凡是 Prompt 里出现的 `{...}` 变量，都必须在
> `format_messages()` / `format()` 时显式传值，否则会抛 KeyError。

#### 陷阱 3：多任务混合

```text
# ❌ 一个 Prompt 做多件事
请清洗数据、评估质量、提取知识、生成报告。

# ✅ 分解为多个 Agent
1. 清洗 Agent：只负责清洗
2. 评估 Agent：只负责评估
3. 提取 Agent：只负责提取
4. 报告 Agent：只负责报告
```

---

## 7. 常见问题

### Q1：Prompt 应该多长？

**A**：
- System Prompt: 500-1500 tokens（过长会稀释重点）
- User Prompt: 尽可能短，包含必要信息即可
- 总长度: 尽量 < 2000 tokens（输入）

### Q2：什么时候更新 Prompt？

**A**：
- ✅ 发现准确率下降
- ✅ 用户反馈问题
- ✅ 新增功能
- ✅ A/B 测试证明新版本更好
- ❌ 不要频繁改动（每次改动都要测试）

### Q3：如何选择 Few-shot 示例数量？

**A**：
- **默认 2-3 条**（本项目统一口径，所有 Agent 的 `examples.json` 按此准备）
- 0-shot：极简单任务（如二分类）可不用示例
- 4 条以上：收益递减，且显著增加 Token 成本，不推荐
- 覆盖原则：2-3 条示例应分别覆盖「典型正常样本」+「边界/异常样本」

### Q4：如何处理多语言？

**A**：
```
prompts/
├── cleaning/
│   ├── system_zh.txt     # 中文
│   ├── system_en.txt     # 英文
│   └── system_ja.txt     # 日文
```

### Q5：Prompt 可以包含代码吗？

**A**：可以，但要用 markdown 代码块标注：

```text
输出格式示例：
```json
{
  "field": "value"
}
```
```

---

## 8. 总结

### 核心要点

1. **Prompt 是代码**：像管理代码一样管理 Prompt
2. **版本控制**：每个变更都有版本号和测试
3. **测试驱动**：先写测试用例，再写 Prompt
4. **持续优化**：基于数据迭代，不是拍脑袋
5. **文档完善**：让其他人能理解和修改

### Prompt 工程清单

开发新 Agent 时，确保：

- [ ] 创建独立的 Prompt 目录
- [ ] 编写 system.txt（角色+任务+格式+规则）
- [ ] 准备 examples.json（2-3 个，字段名 input / expected_output）
- [ ] 创建 version.txt（v1.0.0）
- [ ] 编写 Prompt 测试用例（每维度 ≥10 个，合计 ≥50 个）
- [ ] 运行测试（通过率 > 95%）
- [ ] 记录性能指标（准确率、Token、成本口径：按实际模型单价重算）
- [ ] 编写 README（使用说明）

---

**遵循 Prompt 工程规范，构建高质量的 AI Agent！** 🚀
