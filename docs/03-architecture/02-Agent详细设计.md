# AI Insight Hub - Agent 详细设计

> **文档版本**：v1.0  
> **创建日期**：2026年10月23日  
> **最后更新**：2026年10月23日  
> **状态**：设计阶段

---

## 📋 目录

1. [Agent 架构概述](#1-agent-架构概述)
2. [Agent 1: 数据清洗 Agent](#2-agent-1-数据清洗-agent)
3. [Agent 2: 质量评估 Agent](#3-agent-2-质量评估-agent)
4. [Agent 3: 知识提取 Agent](#4-agent-3-知识提取-agent)
5. [Agent 4: 洞察分析 Agent](#5-agent-4-洞察分析-agent)
6. [Agent 5: 报告生成 Agent](#6-agent-5-报告生成-agent)
7. [Agent 协作工作流](#7-agent-协作工作流)
8. [通用设计规范](#8-通用设计规范)

---

## 1. Agent 架构概述

### 1.1 Agent 层级关系

```
┌────────────────────────────────────────────────────────────┐
│                       Agent Layer                          │
│  ┌──────────┐   ┌────────────┐   ┌────────────┐            │
│  │ Cleaning │ → │ Evaluation │ → │ Extraction │            │
│  │  Agent   │   │   Agent    │   │   Agent    │            │
│  └──────────┘   └────────────┘   └────────────┘            │
│                                        │                    │
│                                        ↓                    │
│  ┌──────────┐                  ┌────────────┐              │
│  │  Report  │ ←─────────────── │  Insight   │              │
│  │  Agent   │                  │   Agent    │              │
│  └──────────┘                  └────────────┘              │
└────────────────────────────────────────────────────────────┘
               ↓
┌────────────────────────────────────────────────────────────┐
│                      Tools Layer                           │
│  Parser | Validator | Database | File I/O | Retrieval      │
└────────────────────────────────────────────────────────────┘
```

**执行顺序（与 7.1 节 LangGraph 工作流一致）**：

```
Clean → Evaluate →［overall_score < 70 时插入人工复核 Manual Review］→ Extract → Insight → Report
```

> 注：Evaluation 之后是 **Insight** 再 **Report**，Report 不在 Evaluation 之后直接执行；人工复核是条件分支（见 7.1 节）。

---

### 1.2 Agent 统一接口

**BaseAgent 抽象类**：

```python
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from langchain_deepseek import ChatDeepSeek
from pydantic import BaseModel

from app.core.config import settings

class AgentConfig(BaseModel):
    """Agent 配置"""
    name: str
    version: str
    # 模型 id 不写死：统一由 settings.DEFAULT_LLM_MODEL 提供（默认 deepseek-v4.1-flash）
    model: str = settings.DEFAULT_LLM_MODEL
    # 结构化输出（清洗/评估/提取）用 0.0；洞察/报告类可单独覆盖为 0.3
    temperature: float = settings.DEFAULT_TEMPERATURE
    max_tokens: int = 4096
    timeout: int = 60              # 单次调用超时（秒）
    max_retries: int = 3           # 失败重试次数（指数退避，见 invoke）
    retry_base_delay: float = 1.0  # 首次退避秒数，此后 ×2（1s → 2s → 4s）

class AgentResult(BaseModel):
    """Agent 执行结果"""
    success: bool
    data: Dict[str, Any]
    metadata: Dict[str, Any]
    errors: List[str] = []
    warnings: List[str] = []
    
    # 性能指标
    duration: float  # 秒
    token_usage: Dict[str, int]  # {input: x, output: y}
    cost: float  # 美元（= 实际模型单价 × token，单价不入代码）

# ---------------- 统一异常体系 ----------------
class AgentError(Exception):
    """所有 Agent 异常的基类；retryable 决定 invoke 是否重试"""

    def __init__(self, message: str, agent_name: str = "", retryable: bool = False):
        super().__init__(message)
        self.message = message
        self.agent_name = agent_name
        self.retryable = retryable

class AgentInputError(AgentError):
    """输入校验失败（不可重试）"""

class AgentOutputError(AgentError):
    """输出校验/解析失败（可重试：重新生成一次）"""

class AgentTimeoutError(AgentError):
    """调用超时（可重试）"""

class AgentExecutionError(AgentError):
    """执行期异常（LLM/工具/网络，可重试）"""

# 各 Agent 的业务子类：统一继承上面的基类，禁止再定义游离于体系之外的异常
class CleaningError(AgentExecutionError):
    """清洗 Agent 错误基类"""

class ParseError(CleaningError):
    """解析错误（不可重试，跳过该条）"""

class CleaningValidationError(AgentOutputError):
    """清洗输出校验失败"""

class EvaluationError(AgentExecutionError):
    """质量评估 Agent 错误"""

class ExtractionError(AgentExecutionError):
    """知识提取 Agent 错误"""

class InsightError(AgentExecutionError):
    """洞察分析 Agent 错误"""

class ReportError(AgentExecutionError):
    """报告生成 Agent 错误"""

class BaseAgent(ABC):
    """所有 Agent 的基类"""
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.llm = self._init_llm()
        self.tools = self._init_tools()
        self.prompt = self._load_prompt()
        self.agent = self._create_agent()

    def _init_llm(self) -> ChatDeepSeek:
        """初始化 LLM（统一走 langchain-deepseek）"""
        return ChatDeepSeek(
            model=self.config.model,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            timeout=self.config.timeout,
        )
    
    @abstractmethod
    def _init_tools(self) -> List[Any]:
        """初始化工具（子类实现）"""
        pass
    
    @abstractmethod
    def _load_prompt(self) -> Any:
        """加载 Prompt（子类实现）"""
        pass
    
    @abstractmethod
    def _create_agent(self) -> Any:
        """创建执行链（子类实现）

        返回 LangChain Runnable（LCEL 链 / LangGraph 节点）。
        """
        pass
    
    @abstractmethod
    def _validate_input(self, input_data: Dict[str, Any]) -> bool:
        """验证输入（子类实现）"""
        pass
    
    @abstractmethod
    def _validate_output(self, output_data: Dict[str, Any]) -> bool:
        """验证输出（子类实现）"""
        pass
    
    def invoke(
        self,
        input_data: Dict[str, Any],
        callbacks: Optional[List] = None
    ) -> AgentResult:
        """执行 Agent（统一入口：校验 → 带超时/重试执行 → 校验输出 → 封装结果）"""
        import time

        # 1. 输入验证（失败直接返回，不重试）
        try:
            if not self._validate_input(input_data):
                raise AgentInputError("输入验证失败", self.config.name)
        except AgentError as exc:
            return self._fail(exc, duration=0.0)

        # 2. 执行（指数退避重试，最多 max_retries 次）
        start_time = time.time()
        last_error: Optional[Exception] = None

        for attempt in range(self.config.max_retries + 1):
            try:
                result = self._invoke_once(input_data, callbacks)
                duration = time.time() - start_time

                # 3. 输出验证
                if not self._validate_output(result):
                    raise AgentOutputError(
                        "输出验证失败", self.config.name, retryable=True
                    )

                # 4. 返回
                return AgentResult(
                    success=True,
                    data=result,
                    metadata=self._extract_metadata(result),
                    duration=duration,
                    token_usage=self._extract_token_usage(result),
                    cost=self._calculate_cost(result),
                )

            except AgentError as exc:
                last_error = exc
                if attempt >= self.config.max_retries or not exc.retryable:
                    break
                # 指数退避：1s → 2s → 4s（与服务端限流/瞬时故障错开）
                time.sleep(self.config.retry_base_delay * (2 ** attempt))

        return self._fail(
            last_error or AgentExecutionError("未知错误", self.config.name),
            duration=time.time() - start_time,
        )

    def _invoke_once(
        self,
        input_data: Dict[str, Any],
        callbacks: Optional[List] = None,
    ) -> Dict[str, Any]:
        """单次调用；超时由 ChatDeepSeek(timeout=config.timeout) 控制

        统一把底层异常（超时 / 网络 / 限流）翻译成 AgentError 子类，
        否则它们会绕过 invoke() 的 except AgentError 分支直接抛出。
        """
        try:
            return self.agent.invoke(
                input_data,
                config={"callbacks": callbacks or []},
            )
        except AgentError:
            raise
        except TimeoutError as exc:
            raise AgentTimeoutError(
                str(exc), self.config.name, retryable=True
            ) from exc
        except Exception as exc:
            raise AgentExecutionError(
                str(exc), self.config.name, retryable=True
            ) from exc

    def _fail(self, error: Exception, duration: float) -> AgentResult:
        """统一失败结果封装"""
        return AgentResult(
            success=False,
            data={},
            metadata={"error": str(error), "agent": self.config.name},
            errors=[str(error)],
            duration=duration,
            token_usage={},
            cost=0.0,
        )
```

> **重试与超时口径**：
> 1. 与 `docs/04-development/07-Agent错误重试机制.md` 的 `async_retry` 装饰器同口径（最多 3 次、指数退避 + Jitter、1s 起）；本类在同步 `invoke()` 内联实现同一语义，异步 Agent 直接用该文档的装饰器。
> 2. 单次调用超时 = `AgentConfig.timeout`（默认 60s），由 `ChatDeepSeek(timeout=...)` 传入；超时抛 `AgentTimeoutError(retryable=True)`。
> 3. 只有 `retryable=True` 的异常才重试；`AgentInputError`、`ParseError` 一律不重试。
> 4. 重试必须幂等：`AgentResult` 的写库动作（`analysis_results` / `cost_tracking`）由调用方在一次逻辑成功后统一落库，避免重试导致重复计费（详见 07 文档的幂等性要求）。

---

## 2. Agent 1: 数据清洗 Agent

### 2.1 功能概述

**职责**：将非结构化的客服对话数据转换为标准化的 JSON 格式

**输入**：原始数据（CSV/TXT/JSON）
**输出**：标准化 JSON + 质量评分

---

### 2.2 详细设计

#### 输入 Schema

```python
from pydantic import BaseModel, Field
from typing import Optional

class CleaningInput(BaseModel):
    """数据清洗输入"""
    datasource_id: str = Field(..., description="数据源 ID")
    raw_data: str = Field(..., description="原始数据文本")
    data_type: str = Field(
        default="unknown",
        description="数据类型：csv/json/text"
    )
    config: Optional[dict] = Field(
        default={},
        description="清洗配置"
    )
```

#### 输出 Schema

```python
from uuid import UUID
from datetime import datetime
from typing import List

class CleanedDialogue(BaseModel):
    """清洗后的对话"""
    dialogue_id: UUID
    timestamp: datetime
    user_message: str
    ai_response: str
    metadata: dict
    quality_score: float  # 0-100
    issues: List[str]

class CleaningOutput(BaseModel):
    """数据清洗输出"""
    datasource_id: str
    total_records: int
    cleaned_records: int
    failed_records: int
    dialogues: List[CleanedDialogue]
    statistics: dict
```

---

#### 工具列表

```python
def _init_tools(self) -> List[Tool]:
    return [
        Tool(
            name="parse_csv",
            description="解析 CSV 格式数据",
            func=self._parse_csv
        ),
        Tool(
            name="parse_json",
            description="解析 JSON 格式数据",
            func=self._parse_json
        ),
        Tool(
            name="detect_duplicates",
            description="检测重复对话（相似度 > 95%）",
            func=self._detect_duplicates
        ),
        Tool(
            name="normalize_text",
            description="文本规范化（去空格、全角转半角等）",
            func=self._normalize_text
        ),
        Tool(
            name="extract_timestamp",
            description="提取和解析时间戳",
            func=self._extract_timestamp
        )
    ]
```

**工具实现示例**：

```python
def _detect_duplicates(self, dialogues: List[dict]) -> List[int]:
    """检测重复对话"""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    
    # 构建文本
    texts = [
        f"{d['user_message']} {d['ai_response']}"
        for d in dialogues
    ]
    
    # 计算相似度
    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform(texts)
    similarity_matrix = cosine_similarity(tfidf_matrix)
    
    # 找出重复（相似度 > 0.95）
    duplicates = []
    for i in range(len(similarity_matrix)):
        for j in range(i + 1, len(similarity_matrix)):
            if similarity_matrix[i][j] > 0.95:
                duplicates.append(j)
    
    return list(set(duplicates))

def _normalize_text(self, text: str) -> str:
    """文本规范化"""
    import re
    
    # 去除前后空白
    text = text.strip()
    
    # 全角转半角
    text = text.translate(str.maketrans(
        '，。！？；：（）【】""''',
        ',.!?;:()[]"\'\''
    ))
    
    # 移除 HTML 标签
    text = re.sub(r'<[^>]+>', '', text)
    
    # 规范化空白字符
    text = re.sub(r'\s+', ' ', text)
    
    return text
```

---

#### Prompt 位置

```
prompts/cleaning/
├── system.txt              # 主 Prompt
├── examples.json           # Few-shot 示例
└── version.txt             # v1.0.0
```

---

#### 状态机

```python
from enum import Enum

class CleaningState(Enum):
    PENDING = "pending"
    PARSING = "parsing"
    DEDUPLICATING = "deduplicating"
    NORMALIZING = "normalizing"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
```

---

#### 性能指标

| 指标 | 目标 | 说明 |
|------|------|------|
| **准确率** | > 95% | 正确提取字段的比例 |
| **速度** | ≥ 1000 条/分钟（批处理） | 单条 ≈ 50 ms（批内并发）；串行单条口径见下方说明 |
| **去重准确率** | > 90% | 正确识别重复的比例 |
| **Token 消耗** | < 500/条 | 平均 Token 使用 |
| **成本** | 按实际模型单价重算 | 单条成本 = 实际单价 × 实测 Token，本文档不写死金额 |
| **超时/重试** | 60s / 3 次 | 指数退避 1s→2s→4s（`AgentConfig.timeout` / `max_retries`） |

> **速度口径统一**：`≥ 1000 条/分钟` 是**批处理吞吐**口径（20 条/批、批内并发）；`docs/02-design/01-Prompt工程规范.md` 中「平均耗时 1.2 秒/条」是**单条串行**口径（≈50 条/分钟）。两者不矛盾但不可混用——对外统一写「批处理 ≥ 1000 条/分钟」，单条串行值标注为「≈ 1.2 s（待实测确认）」。

---

#### 错误处理

```python
# 异常类已在 §1.2「统一异常体系」定义，此处不重复声明：
#   CleaningError（基类）/ ParseError（解析失败，不可重试）
#   CleaningValidationError（输出校验失败，可重试）/ AgentExecutionError（LLM/网络异常，可重试）

# 错误处理策略
ERROR_HANDLING = {
    ParseError: "skip",                # 跳过该条，继续处理（计入 failed_records）
    CleaningValidationError: "retry",  # 重试，最多 max_retries 次
    AgentExecutionError: "retry",      # 指数退避重试
    Exception: "fail",                 # 整体失败，写 agent_failures 并告警
}
```

---

## 3. Agent 2: 质量评估 Agent

### 3.1 功能概述

**职责**：评估 AI 客服回复的质量

**输入**：清洗后的对话 + 知识库（可选）
**输出**：质量评分 + 问题列表 + 改进建议

---

### 3.2 评估维度

```python
class EvaluationDimension(BaseModel):
    """评估维度"""
    name: str
    score: float  # 0-100
    weight: float  # 权重 0-1
    issues: List[str]
    examples: List[str]

# 5 个评估维度
DIMENSIONS = {
    "accuracy": {
        "name": "准确性",
        "weight": 0.35,
        "description": "回答是否正确，有无事实错误"
    },
    "completeness": {
        "name": "完整性",
        "weight": 0.25,
        "description": "是否充分回答，有无遗漏"
    },
    "hallucination": {
        "name": "幻觉检测",
        "weight": 0.20,
        "description": "是否编造信息"
    },
    "tone": {
        "name": "语气礼貌度",
        "weight": 0.10,
        "description": "是否礼貌、有同理心"
    },
    "compliance": {
        "name": "合规性",
        "weight": 0.10,
        "description": "是否违规、泄露敏感信息"
    }
}
```

---

### 3.3 详细设计

#### 输入 Schema

```python
class EvaluationInput(BaseModel):
    """质量评估输入"""
    dialogue: CleanedDialogue
    knowledge_base: Optional[List[dict]] = None  # 用于验证准确性
    evaluation_config: dict = {
        "dimensions": ["accuracy", "completeness", "hallucination", "tone", "compliance"],
        "threshold": 70  # 低于此分数标记为问题
    }
```

#### 输出 Schema

```python
class EvaluationOutput(BaseModel):
    """质量评估输出"""
    dialogue_id: UUID
    overall_score: float  # 加权总分 0-100
    dimensions: Dict[str, EvaluationDimension]
    
    # 问题
    has_issues: bool
    critical_issues: List[str]  # 严重问题
    minor_issues: List[str]     # 一般问题
    
    # 建议
    suggestions: List[str]
    
    # 分类
    quality_level: str  # excellent/good/acceptable/poor
    needs_review: bool  # 是否需要人工审核
```

---

#### 工具列表

```python
def _init_tools(self) -> List[Tool]:
    return [
        Tool(
            name="search_knowledge_base",
            description="在知识库中搜索相关信息",
            func=self._search_kb
        ),
        Tool(
            name="detect_hallucination",
            description="检测是否有幻觉（编造信息）",
            func=self._detect_hallucination
        ),
        Tool(
            name="analyze_sentiment",
            description="分析语气和情感",
            func=self._analyze_sentiment
        ),
        Tool(
            name="check_compliance",
            description="检查合规性（敏感词、违规内容）",
            func=self._check_compliance
        )
    ]
```

**工具实现示例**：

```python
def _detect_hallucination(
    self,
    ai_response: str,
    knowledge_base: List[dict]
) -> Dict[str, Any]:
    """幻觉检测"""
    
    # 1. 提取 AI 回复中的事实性陈述
    facts = self._extract_factual_claims(ai_response)
    
    # 2. 在知识库中验证
    hallucinations = []
    for fact in facts:
        if not self._verify_fact(fact, knowledge_base):
            hallucinations.append(fact)
    
    return {
        "has_hallucination": len(hallucinations) > 0,
        "hallucinated_claims": hallucinations,
        "confidence": 0.85 if hallucinations else 0.95
    }

def _check_compliance(self, text: str) -> Dict[str, Any]:
    """合规性检查"""
    
    # 敏感词库
    SENSITIVE_PATTERNS = [
        r'\d{17}[\dXx]',           # 身份证
        r'\d{16,19}',              # 银行卡
        r'1[3-9]\d{9}',            # 手机号
        r'password[:=]\s*\S+',     # 密码
    ]
    
    violations = []
    for pattern in SENSITIVE_PATTERNS:
        if re.search(pattern, text):
            violations.append(f"包含敏感信息: {pattern}")
    
    return {
        "is_compliant": len(violations) == 0,
        "violations": violations
    }
```

---

#### Prompt 位置

```
prompts/evaluation/
├── system.txt
├── dimensions/
│   ├── accuracy.txt          # 准确性评估子 Prompt
│   ├── completeness.txt
│   ├── hallucination.txt
│   ├── tone.txt
│   └── compliance.txt
├── examples.json
└── version.txt
```

---

#### 评分算法

```python
def _calculate_overall_score(
    self,
    dimension_scores: Dict[str, float]
) -> float:
    """计算加权总分

    只对「本次启用的维度」加权，并按启用维度的权重之和**重新归一化**；
    否则裁剪某个维度（如不跑 compliance）后总分会被系统性压低。
    """

    enabled = {
        name: score
        for name, score in dimension_scores.items()
        if name in DIMENSIONS
    }
    if not enabled:
        return 0.0

    total_weight = sum(DIMENSIONS[name]["weight"] for name in enabled)
    if total_weight <= 0:
        return 0.0

    total_score = sum(
        score * DIMENSIONS[name]["weight"]
        for name, score in enabled.items()
    )

    # 除以实际启用维度的权重和，保证「5 维全开」与「只开 3 维」都落在 0-100
    return round(total_score / total_weight, 2)

def _classify_quality(self, score: float) -> str:
    """质量分级（展示口径，阈值定义见下方「阈值定义表」）"""
    if score >= 90:
        return "excellent"
    elif score >= 75:
        return "good"
    elif score >= 60:
        return "acceptable"
    else:
        return "poor"
```

**示例（5 维全开）**：accuracy 90、completeness 80、hallucination 95、tone 85、compliance 100
→ `90×0.35 + 80×0.25 + 95×0.20 + 85×0.10 + 100×0.10 = 31.5 + 20 + 19 + 8.5 + 10 = 89.0` → `good`。

**示例（只启用 3 维：accuracy / completeness / hallucination）**：权重和 = 0.80，`(31.5 + 20 + 19) / 0.80 = 88.13`，而不是直接得 70.5。

---

#### 阈值定义表（统一口径）

| 阈值 | 取值 | 作用 | 说明 |
|------|------|------|------|
| 维度低分阈值 `evaluation_config.threshold` | **70** | 单个维度 `score < 70` 时，该维度的问题计入 `critical_issues` | 决定「哪些问题算严重问题」 |
| 人工审核阈值 `needs_review` | **70** | `overall_score < 70` → `needs_review = True`，工作流转 `manual_review` 分支 | 与上一行同值，避免两套数字打架 |
| 分级 excellent | **≥ 90** | 报告展示 | 仅用于展示与统计，不参与流程分流 |
| 分级 good | **75 – 89.99** | 报告展示 | |
| 分级 acceptable | **60 – 74.99** | 报告展示 | |
| 分级 poor | **< 60** | 报告展示 | |

> **两套阈值为何并存**：`quality_level` 是「报告展示口径」（4 档），`needs_review` 是「流程分流口径」（二元）。
> 由于两者都落在 0-100 分，统一取 **70** 作为人工审核线，因此会出现「acceptable（60-74.99）但需要人工复核」的组合——这是**预期行为**，不是矛盾。
> 修改任一阈值时必须同步改本表与 `EvaluationInput.evaluation_config` 的默认值。

---

#### 性能指标

| 指标 | 目标 |
|------|------|
| **准确率** | > 85% |
| **召回率** | > 90%（问题检出率）|
| **速度** | < 2 秒/条 |
| **Token 消耗** | < 800/条 |
| **成本** | 按实际模型单价重算（实际单价 × 实测 Token） |
| **超时/重试** | 60s / 3 次（指数退避 1s→2s→4s） |

---

#### 错误处理

```python
# 异常定义见 §1.2：EvaluationError（LLM/工具异常，可重试）/ AgentOutputError（JSON 解析失败，可重试）
ERROR_HANDLING = {
    EvaluationError: "retry",       # 重试到 max_retries 次
    AgentOutputError: "retry",      # 结构化输出不合法 → 重试一次
    AgentInputError: "fail",        # 输入缺 dialogue → 直接失败，不重试
    Exception: "fail",              # 写 agent_failures 并告警
}

# 抽取不到知识库依据（knowledge_base 为空）时的降级：
# hallucination 维度记 neutral（70 分）并在 suggestions 中提示「缺少知识库依据，建议补录」
```

---

## 4. Agent 3: 知识提取 Agent

### 4.1 功能概述

**职责**：从对话数据中提取知识，构建 FAQ 知识库

**输入**：清洗后的对话列表
**输出**：FAQ 列表 + 知识盲区报告

---

### 4.2 详细设计

#### 输入 Schema

```python
class ExtractionInput(BaseModel):
    """知识提取输入"""
    dialogues: List[CleanedDialogue]
    datasource_id: str
    config: dict = {
        "min_frequency": 3,      # 最少出现 3 次才提取
        "similarity_threshold": 0.85,  # 问题聚类阈值
        "max_faq_count": 100     # 最多提取 100 个 FAQ
    }
```

#### 输出 Schema

```python
class FAQ(BaseModel):
    """FAQ 条目"""
    id: UUID
    question: str
    answer: str
    category: str  # 产品/售后/咨询
    frequency: int  # 出现次数
    confidence: float  # 0-1
    source_dialogue_ids: List[UUID]
    variations: List[str]  # 问题的不同表述
    embedding: Optional[List[float]]  # 向量表示

class KnowledgeGap(BaseModel):
    """知识盲区"""
    question: str
    frequency: int
    category: str
    priority: str  # high/medium/low
    suggested_answer: Optional[str]

class ExtractionOutput(BaseModel):
    """知识提取输出"""
    datasource_id: str
    faq_list: List[FAQ]
    knowledge_gaps: List[KnowledgeGap]
    statistics: dict
```

---

#### 工具列表

```python
def _init_tools(self) -> List[Tool]:
    return [
        Tool(
            name="extract_questions",
            description="从对话中提取用户问题",
            func=self._extract_questions
        ),
        Tool(
            name="cluster_similar_questions",
            description="聚类相似问题",
            func=self._cluster_questions
        ),
        Tool(
            name="extract_standard_answer",
            description="从多个回复中提取标准答案",
            func=self._extract_answer
        ),
        Tool(
            name="categorize_faq",
            description="对 FAQ 进行分类",
            func=self._categorize
        ),
        Tool(
            name="generate_embedding",
            description="生成问题的向量表示",
            func=self._generate_embedding
        )
    ]
```

**工具实现示例**：

```python
def _cluster_questions(
    self,
    questions: List[str],
    threshold: float = 0.85
) -> List[List[int]]:
    """聚类相似问题"""
    from sklearn.cluster import DBSCAN
    from sentence_transformers import SentenceTransformer
    
    # 生成嵌入：paraphrase-multilingual-MiniLM-L12-v2 输出 384 维，
    # 与 knowledge_base.embedding VECTOR(384) 严格对齐（见下方「向量维度冻结」说明）
    model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    embeddings = model.encode(questions)  # shape = (n, 384)
    
    # 聚类
    clustering = DBSCAN(
        eps=1 - threshold,
        min_samples=2,
        metric='cosine'
    )
    clusters = clustering.fit_predict(embeddings)
    
    # 组织结果
    result = {}
    for idx, cluster_id in enumerate(clusters):
        if cluster_id not in result:
            result[cluster_id] = []
        result[cluster_id].append(idx)
    
    return list(result.values())

def _extract_answer(
    self,
    answers: List[str]
) -> str:
    """从多个回复中提取标准答案"""
    
    # 使用 LLM 提取最佳答案
    prompt = f"""
    以下是针对同一个问题的多个 AI 回复：
    
    {chr(10).join(f"{i+1}. {a}" for i, a in enumerate(answers))}
    
    请提取出最准确、最完整的标准答案。
    """
    
    # ChatDeepSeek.invoke 返回 BaseMessage，取 content 才是文本
    return self.llm.invoke(prompt).content
```

> **向量维度冻结（与数据库设计一致）**
>
> | 项 | 冻结值 | 说明 |
> |---|---|---|
> | 嵌入模型 | `paraphrase-multilingual-MiniLM-L12-v2` | 本地推理，无需外部 API |
> | 向量维度 | **384** | 该模型固定输出 384 维 |
> | 列类型 | **`VECTOR(384)`** | `knowledge_base.embedding`、`cleaned_data.embedding` 均为 `VECTOR(384)`，与 `docs/03-architecture/03-数据库设计.md` 一致；写成其它维度会直接插入失败 |
> | 索引 | **HNSW** | `USING hnsw (embedding vector_cosine_ops)`（余弦距离），与 `backend/scripts/init_db.sql`、数据库设计一致 |
>
> ⚠️ 改嵌入模型 = 改维度 = 必须重建列与索引（`ALTER TABLE ... ALTER COLUMN embedding TYPE VECTOR(新维度)` + 全量重算 embedding），不能只换模型。

---

#### 工作流程

```
1. 提取问题
   ↓
2. 问题聚类（相似问题合并）
   ↓
3. 提取标准答案
   ↓
4. FAQ 分类
   ↓
5. 生成向量嵌入
   ↓
6. 识别知识盲区（无法回答的问题）
```

---

#### Prompt 位置

```
prompts/extraction/
├── system.txt
├── tasks/
│   ├── question_extraction.txt
│   ├── answer_synthesis.txt
│   └── gap_analysis.txt
├── examples.json
└── version.txt
```

---

#### 性能指标

| 指标 | 目标 |
|------|------|
| **提取准确率** | > 80% |
| **聚类准确率** | > 85% |
| **知识盲区覆盖率** | > 85%（口径待确认：确认方式＝人工标注盲区集合 vs 系统输出的召回率） |
| **处理速度** | 100 条对话/分钟 |
| **Token 消耗** | < 2000/100 条（待实测确认） |
| **成本** | 按实际模型单价重算（实际单价 × 实测 Token） |
| **超时/重试** | 60s / 3 次（指数退避 1s→2s→4s） |

---

#### 错误处理

```python
# 异常定义见 §1.2：ExtractionError（LLM/工具异常，可重试）/ AgentOutputError（输出不合法，可重试）
ERROR_HANDLING = {
    ExtractionError: "retry",
    AgentOutputError: "retry",
    AgentInputError: "fail",       # 空对话列表直接返回空结果，不重试
    Exception: "fail",
}

# 单条 FAQ 生成向量失败（模型 OOM 等）时：该条 status 置为 'needs_review'，不阻塞整批
```

---

## 5. Agent 4: 洞察分析 Agent

### 5.1 功能概述

**职责**：分析客户诉求、情感趋势、痛点

**输入**：清洗后的对话列表
**输出**：洞察报告（诉求分布、情感分析、趋势、痛点）

---

### 5.2 详细设计

#### 输入 Schema

```python
class InsightInput(BaseModel):
    """洞察分析输入"""
    dialogues: List[CleanedDialogue]
    datasource_id: str
    time_range: Optional[dict] = None  # {start, end}
    config: dict = {
        "analyze_sentiment": True,
        "identify_trends": True,
        "find_pain_points": True
    }
```

#### 输出 Schema

```python
class InsightOutput(BaseModel):
    """洞察分析输出"""
    datasource_id: str
    
    # 诉求分析（计数口径：单位＝条数）
    intent_distribution: Dict[str, int]  # {咨询: 45, 投诉: 30, ...}
    top_questions: List[dict]  # 高频问题：[{question, count, ratio}]
    
    # 情感分析（占比口径：0-1 的小数，三类之和 = 1.0；不要再写百分数）
    sentiment_distribution: Dict[str, float]  # {正面: 0.40, 中性: 0.50, 负面: 0.10}
    sentiment_trend: List[dict]  # 时间序列：[{date, positive: 0.4, neutral: 0.5, negative: 0.1}]
    
    # 痛点分析
    pain_points: List[dict]
    unresolved_issues: List[dict]
    
    # 趋势
    emerging_topics: List[str]
    seasonal_patterns: Optional[dict]
```

---

#### 工具列表

```python
def _init_tools(self) -> List[Tool]:
    return [
        Tool(
            name="classify_intent",
            description="分类用户意图（咨询/投诉/建议等）",
            func=self._classify_intent
        ),
        Tool(
            name="analyze_sentiment",
            description="情感分析",
            func=self._analyze_sentiment
        ),
        Tool(
            name="identify_pain_points",
            description="识别客户痛点",
            func=self._identify_pain_points
        ),
        Tool(
            name="detect_trends",
            description="检测趋势变化",
            func=self._detect_trends
        )
    ]
```

---

#### Prompt 位置

```
prompts/insight/
├── system.txt
├── tasks/
│   ├── intent_classification.txt
│   ├── sentiment_analysis.txt
│   ├── pain_point_detection.txt
│   └── trend_analysis.txt
├── examples.json
└── version.txt
```

---

#### 配置（temperature 例外）

```python
# 洞察属于「分析/生成」类，允许比结构化输出更高的温度
INSIGHT_CONFIG = AgentConfig(
    name="insight_agent",
    version="v1.0.0",
    temperature=0.3,   # 覆盖 settings.DEFAULT_TEMPERATURE(0.0)
    max_tokens=4096,
    timeout=120,       # 分析类批量输入，超时放宽到 120s
    max_retries=3,
)
```

---

#### 性能指标

| 指标 | 目标 | 说明 |
|------|------|------|
| **意图分类准确率** | > 85% | 与人工标注抽检对比 |
| **情感分析准确率** | > 80% | 三分类（正/中/负） |
| **痛点识别召回率** | > 75%（待确认） | 确认方式：人工标注痛点集合做基准 |
| **处理速度** | < 5 秒/100 条 | 批量聚合分析 |
| **Token 消耗** | < 3000/100 条（待实测确认） | 输入含对话摘要，成本随条数线性增长 |
| **成本** | 按实际模型单价重算 | 单次成本 = 实际单价 × 实测 Token，本文档不写死金额 |
| **超时/重试** | 120s / 3 次 | 指数退避 1s→2s→4s |

---

#### 错误处理

```python
# 异常定义见 §1.2：InsightError（LLM/工具异常，可重试）/ AgentOutputError（JSON 不合法，可重试）
ERROR_HANDLING = {
    InsightError: "retry",
    AgentOutputError: "retry",
    AgentInputError: "fail",
    Exception: "fail",
}

# 降级策略：
# 1. 情感分析失败 → sentiment_distribution 置空并标 degraded=true，其余维度照常输出；
# 2. 趋势分析失败（样本时间跨度 < 2 天）→ sentiment_trend 返回空数组，不视为错误；
# 3. 整节点失败 → 工作流跳过 Insight 直接进入 Report，报告里标注「洞察分析缺失」。
```

---

#### 状态机

```python
from enum import Enum

class InsightState(Enum):
    PENDING = "pending"
    CLASSIFYING = "classifying"      # 意图分类
    SENTIMENT = "sentiment"          # 情感分析
    PAIN_POINTS = "pain_points"      # 痛点识别
    TRENDING = "trending"            # 趋势检测
    COMPLETED = "completed"
    DEGRADED = "degraded"            # 部分维度失败
    FAILED = "failed"
```

---

## 6. Agent 5: 报告生成 Agent

### 6.1 功能概述

**职责**：生成专业的分析报告

**输入**：所有分析结果
**输出**：PDF/Excel/Markdown 报告

---

### 6.2 详细设计

#### 输入 Schema

```python
class ReportData(BaseModel):
    """报告聚合数据（由工作流状态组装，字段与各 Agent 输出一一对应）"""
    cleaning_statistics: dict = {}          # 来源：CleaningOutput.statistics
    quality_summary: dict = {}              # 来源：EvaluationOutput 聚合
                                            # {avg_score, level_distribution, top_issues, needs_review_count}
    knowledge_summary: dict = {}            # 来源：ExtractionOutput.statistics + 知识盲区 Top N
                                            # {faq_count, gap_count, top_gaps}
    insight_summary: Optional[dict] = None  # 来源：InsightOutput（洞察失败时为 None，报告需降级）
    time_range: Optional[dict] = None       # {start, end}

class ReportInput(BaseModel):
    """报告生成输入"""
    datasource_id: str
    report_type: str  # quality/knowledge/insight/comprehensive
    data: ReportData  # 结构化聚合数据（不再是裸 dict）
    format: str = "pdf"  # pdf/excel/markdown
    config: dict = {
        "include_charts": True,
        "include_recommendations": True
    }
```

#### 输出 Schema

```python
class ReportOutput(BaseModel):
    """报告生成输出"""
    report_id: UUID
    datasource_id: str
    report_type: str
    file_path: str
    file_url: str
    generated_at: datetime   # 落库时写入 reports.created_at，见下方字段映射表
    metadata: dict
```

#### 字段映射（ReportOutput ↔ `reports` 表）

| ReportOutput 字段 | `reports` 表字段（见 `03-数据库设计.md` §3.7） | 说明 |
|---|---|---|
| `report_id` | `id` | 同一个 UUID |
| `datasource_id` | `datasource_id` | |
| `report_type` | `report_type` | 取值 `quality/knowledge/insight/comprehensive` |
| `file_path` | `file_path` | |
| `file_url` | `file_url` | |
| `generated_at` | **`created_at`** | 命名不同，仅在 repository 层做一次映射；`completed_at` 用生成结束时间 |
| `metadata` | `data`（JSONB） | 报告摘要/统计写 `data`；生成参数写 `config` |
| —（`format` 入参） | `format` | `pdf / excel / markdown` |
| —（`AgentResult.duration`） | `generation_duration` | 单位秒 |
| —（服务层补齐） | `user_id` / `title` / `file_size` / `status` / `error_message` | 由 API/服务层写入，Agent 不负责 |

> 统一约定：**Output Schema 用 `generated_at`，数据库列用 `created_at`**；映射只在 repository 层做一次，禁止在 SQL 里直接写 `generated_at`。

---

#### 工具列表

```python
def _init_tools(self) -> List[Tool]:
    return [
        Tool(
            name="render_markdown",
            description="用 Jinja2 渲染报告模板（Markdown）",
            func=self._render_markdown
        ),
        Tool(
            name="export_pdf",
            description="Markdown/HTML 转 PDF（WeasyPrint）",
            func=self._export_pdf
        ),
        Tool(
            name="export_excel",
            description="导出 Excel（openpyxl）",
            func=self._export_excel
        ),
        Tool(
            name="upload_to_minio",
            description="上传报告文件到 MinIO 并返回直链",
            func=self._upload_to_minio
        )
    ]
```

> 注意：报告 Agent **不检索知识库**；所有数据来自 `ReportInput.data`，避免在生成阶段二次查询导致口径不一致。

---

#### 报告模板

```
prompts/report/
├── system.txt
├── templates/
│   ├── quality_report.txt        # 质量报告模板
│   ├── knowledge_report.txt      # 知识库报告模板
│   ├── insight_report.txt        # 洞察报告模板
│   └── comprehensive_report.txt  # 综合报告模板
└── version.txt
```

---

#### 配置（temperature 例外）

```python
# 报告属于「生成」类，允许 0.3 的温度；其余参数继承全局默认
REPORT_CONFIG = AgentConfig(
    name="report_agent",
    version="v1.0.0",
    temperature=0.3,
    max_tokens=4096,
    timeout=120,      # 含 PDF/Excel 渲染与上传
    max_retries=3,
)
```

---

#### 性能指标

| 指标 | 目标 | 说明 |
|------|------|------|
| **模板渲染成功率** | > 99% | 渲染失败即整单失败 |
| **数据完整率** | 100% | 报告中每个章节的数据源必须存在或显式标注「无数据」 |
| **处理速度** | Markdown < 2s / PDF < 10s / Excel < 5s（待实测确认） | 不含 LLM 生成时间 |
| **Token 消耗** | < 3000/份（待实测确认） | 报告正文由模板渲染，LLM 只生成摘要与建议 |
| **成本** | 按实际模型单价重算 | 单份成本 = 实际单价 × 实测 Token |
| **超时/重试** | 120s / 3 次 | 渲染/上传失败按指数退避重试 1s→2s→4s |

---

#### 错误处理

```python
# 异常定义见 §1.2：ReportError（渲染/上传/LLM 异常，可重试）/ AgentOutputError（报告结构不合法）
ERROR_HANDLING = {
    ReportError: "retry",
    AgentOutputError: "retry",
    AgentInputError: "fail",     # 缺 datasource_id / 非法 report_type → 直接失败
    Exception: "fail",
}

# 落库约定：
# 1. 开始生成时写 reports(status='generating')；
# 2. 成功 → status='completed', completed_at=NOW(), generation_duration=AgentResult.duration；
# 3. 失败 → status='failed', error_message=异常信息（同时写 agent_failures 表）；
# 4. 洞察数据缺失（insight_summary is None）→ 报告正常生成，但插入「洞察分析缺失」提示段，status 仍为 completed。
```

---

## 7. Agent 协作工作流

### 7.1 LangGraph 工作流

```python
from typing import List, Optional, TypedDict

from langgraph.graph import END, StateGraph

# ---------------- 状态定义 ----------------
class WorkflowState(TypedDict, total=False):
    """工作流状态

    约定：节点之间只传「已拍平的业务数据」，**不传 AgentResult**。
    每个节点返回一个 dict，键名必须与下面的字段一致（LangGraph 按 key 合并）。
    """
    datasource_id: str
    raw_data: str
    # 与 CleaningOutput.dialogues 同结构（不是另一个字段名）
    cleaned_data: List[CleanedDialogue]
    # 与 EvaluationOutput 同结构（拍平为对象列表，而不是 AgentResult.data）
    evaluation_results: List[EvaluationOutput]
    knowledge_base: List[FAQ]
    knowledge_gaps: List[KnowledgeGap]
    insights: Optional[InsightOutput]
    report: Optional[ReportOutput]
    manual_review_required: bool
    status: str

# ---------------- 节点适配器 ----------------
# Agent.invoke() 返回 AgentResult，节点必须拆开它、只把业务数据写回 state；
# 否则条件函数读 state["evaluation_results"][i]["overall_score"] 时层级不符，直接 KeyError。

def clean_node(state: WorkflowState) -> dict:
    result = cleaning_agent.invoke({
        "datasource_id": state["datasource_id"],
        "raw_data": state["raw_data"],
    })
    if not result.success:
        return {"status": "failed"}
    return {
        "cleaned_data": result.data["dialogues"],   # 键名对齐 CleaningOutput.dialogues
        "status": "cleaned",
    }

def evaluate_node(state: WorkflowState) -> dict:
    evaluation_results = []
    for dialogue in state["cleaned_data"]:
        result = evaluation_agent.invoke({"dialogue": dialogue})
        if result.success:
            evaluation_results.append(result.data)
    return {"evaluation_results": evaluation_results, "status": "evaluated"}

def route_after_evaluation(state: WorkflowState) -> str:
    """条件路由：读已拍平的 state，而不是 AgentResult"""
    results = state.get("evaluation_results", [])
    needs_review = any(
        item["overall_score"] < 70 or item.get("needs_review")
        for item in results
    )
    return "manual_review" if needs_review else "extract"

def manual_review_node(state: WorkflowState) -> dict:
    """人工复核节点（必须在图里 add_node 注册，否则条件边指向它会编译失败）

    生产实现：把低分样本写入 analysis_results 并把任务置为待审核，
    由审核 API 回调后恢复流程；此处只做状态标记。
    """
    return {"manual_review_required": True, "status": "awaiting_review"}

def extract_node(state: WorkflowState) -> dict:
    result = extraction_agent.invoke({
        "datasource_id": state["datasource_id"],
        "dialogues": state["cleaned_data"],
    })
    if not result.success:
        return {"status": "failed"}
    return {
        "knowledge_base": result.data["faq_list"],
        "knowledge_gaps": result.data["knowledge_gaps"],
        "status": "extracted",
    }

def insight_node(state: WorkflowState) -> dict:
    result = insight_agent.invoke({
        "datasource_id": state["datasource_id"],
        "dialogues": state["cleaned_data"],
    })
    # 洞察失败不阻塞报告：降级为 None，由报告节点标注「洞察分析缺失」
    return {
        "insights": result.data if result.success else None,
        "status": "analyzed" if result.success else "degraded",
    }

def report_node(state: WorkflowState) -> dict:
    result = report_agent.invoke({
        "datasource_id": state["datasource_id"],
        "report_type": "comprehensive",
        "data": {
            "cleaning_statistics": {"total": len(state.get("cleaned_data", []))},
            "quality_summary": {
                "avg_score": _avg_score(state.get("evaluation_results", [])),
                "needs_review_count": sum(
                    1
                    for item in state.get("evaluation_results", [])
                    if item.get("needs_review")
                ),
            },
            "knowledge_summary": {"faq_count": len(state.get("knowledge_base", []))},
            "insight_summary": state.get("insights"),
        },
    })
    if not result.success:
        return {"status": "failed"}
    return {"report": result.data, "status": "completed"}

def _avg_score(results: List[EvaluationOutput]) -> float:
    if not results:
        return 0.0
    return round(sum(item["overall_score"] for item in results) / len(results), 2)

# ---------------- 构图 ----------------
workflow = StateGraph(WorkflowState)

# 节点注册：manual_review 必须注册，否则条件边指向一个不存在的节点 → 图编译失败
workflow.add_node("clean", clean_node)
workflow.add_node("evaluate", evaluate_node)
workflow.add_node("manual_review", manual_review_node)
workflow.add_node("extract", extract_node)
workflow.add_node("insight", insight_node)
workflow.add_node("report", report_node)

workflow.set_entry_point("clean")
workflow.add_edge("clean", "evaluate")

# ⚠️ evaluate 之后只保留条件边，绝不能再加 add_edge("evaluate", "extract")：
#    静态边与条件边同时存在时静态边优先，review 分支永远走不到。
workflow.add_conditional_edges(
    "evaluate",
    route_after_evaluation,
    {
        "extract": "extract",
        "manual_review": "manual_review",
    },
)

workflow.add_edge("manual_review", "extract")  # 人工复核通过后继续下游
workflow.add_edge("extract", "insight")
workflow.add_edge("insight", "report")
workflow.add_edge("report", END)

app = workflow.compile()
```

**关键修正说明**：

| 问题 | 修正 |
|------|------|
| 条件边指向 `manual_review`，但从未 `add_node` | 已 `add_node("manual_review", manual_review_node)` |
| `evaluate` 同时被静态边和条件边连接 | 删除静态边，只保留 `add_conditional_edges` |
| 条件函数读 `AgentResult.data` 的层级 | 节点只把业务数据写回 state，`evaluation_results` 为 `List[EvaluationOutput]`，条件函数按 `item["overall_score"]` 读取 |
| 状态字段 `cleaned_data` 与清洗输出 `dialogues` 不一致 | 节点显式 `"cleaned_data": result.data["dialogues"]`，状态字段统一为 `cleaned_data` |
| `evaluation_results` 层级不一致 | 统一为 `List[EvaluationOutput]`（每个元素即评估节点 `result.data`） |

---

### 7.2 数据流

```
原始数据 (CSV/TXT)
    ↓
[清洗 Agent] → 标准化 JSON（cleaned_data）
    ↓
[评估 Agent] → 质量评分 + 问题列表（evaluation_results）
    ↓
  overall_score < 70 或 needs_review ?
    ├── 是 → [人工复核 manual_review] → 复核通过 ─┐
    └── 否 ───────────────────────────────────────┤
                                                  ↓
[提取 Agent] → FAQ + 知识盲区（knowledge_base / knowledge_gaps）
    ↓
[洞察 Agent] → 诉求 / 情感 / 痛点（insights，失败可降级为 None）
    ↓
[报告 Agent] → PDF/Excel/Markdown 报告（report）
```

> 数据流与 7.1 的图一一对应：`Clean → Evaluate →（条件分支）→ Extract → Insight → Report`。
> 每一跳只传业务对象，`AgentResult` 的 `duration / token_usage / cost` 由编排层单独写入 `analysis_results` 与调用记录表，不进 `WorkflowState`。

---

## 8. 通用设计规范

### 8.1 命名规范

```python
# Agent 类命名：{功能}Agent
class DataCleaningAgent(BaseAgent):
    ...

# 方法命名：私有方法以 _ 开头，公共方法不加 _
class BaseAgent(ABC):
    def _init_tools(self):
        ...

    def invoke(self, data):
        ...
```

---

### 8.2 错误处理

```python
# 每个 Agent 都按 §1.2「统一异常体系」处理：AgentError 是唯一基类，
# 业务异常（CleaningError / EvaluationError / ExtractionError / InsightError / ReportError）
# 全部继承它，禁止再出现游离的 AgentExecutionError 之类未定义名字。
try:
    result = agent.invoke(data)
except AgentInputError as e:
    logger.warning(f"[{e.agent_name}] 输入不合法，不重试: {e}")
    raise
except AgentOutputError as e:
    # BaseAgent.invoke 内部已按 max_retries 重试过，走到这里说明仍失败
    logger.warning(f"[{e.agent_name}] 输出校验失败: {e}")
except AgentTimeoutError as e:
    logger.error(f"[{e.agent_name}] 调用超时: {e}")
except AgentExecutionError as e:
    logger.error(f"[{e.agent_name}] 执行失败: {e}")
except AgentError as e:
    logger.error(f"[{e.agent_name}] Agent 失败: {e}")
except Exception as e:
    logger.critical(f"未知错误: {e}", exc_info=True)
    raise AgentExecutionError(str(e), agent_name="unknown") from e
```

**异常 → 处理策略映射**：

| 异常 | 可重试 | 处理 | 是否写 `agent_failures` |
|------|--------|------|------------------------|
| `AgentInputError` | ❌ | 直接返回 400，提示调用方修参数 | 否 |
| `ParseError` | ❌ | 跳过该条，计入 `failed_records` | 仅批量失败率 > 10% 时 |
| `AgentOutputError` | ✅ | 重试 `max_retries` 次，仍失败则降级/失败 | 是 |
| `AgentTimeoutError` | ✅ | 指数退避重试，仍失败则失败 | 是 |
| `AgentExecutionError` | ✅ | 指数退避重试，仍失败则失败 | 是 |

---

### 8.3 日志规范

```python
# 统一使用 Loguru 结构化日志；指标走 Prometheus，调用明细写数据库
from loguru import logger

logger.info(f"[{agent_name}] 开始处理: {datasource_id}")
logger.debug(f"[{agent_name}] 输入数据: {input_data}")
logger.info(f"[{agent_name}] 处理完成: success={result.success} duration={result.duration:.2f}s")
logger.error(f"[{agent_name}] 处理失败: {error}")
```

**可观测三件套（全项目统一）**：

| 手段 | 用途 | 关键点 |
|------|------|--------|
| Loguru 日志 | 运行日志、错误堆栈 | 结构化字段：`agent_name` / `datasource_id` / `trace_id` |
| 数据库 LLM 调用记录 | 每次调用的 model / tokens / cost / duration | 写 `analysis_results`、`prompt_usage_logs`（见 `02-Prompt版本管理方案.md`） |
| Prometheus | 指标聚合与告警 | `agent_invocations_total{agent,status}`、`agent_duration_seconds`、`llm_tokens_total`、`llm_cost_total` |

---

### 8.4 测试要求

每个 Agent 必须有：
- ✅ 单元测试（覆盖率 > 80%）
- ✅ Prompt 测试（每维度 ≥10 用例，合计 ≥50 用例）
- ✅ 集成测试（完整流程）
- ✅ 性能测试（Token/成本/速度）

---

### 8.5 五个 Agent 规格对齐表

> 五个 Agent 必须齐平：功能、输入/输出 Schema、工具、超时/重试、性能指标、成本口径、错误处理。缺项按本表补齐。

| Agent | 功能 | 输入 Schema | 输出 Schema | 工具 | temperature | 超时/重试 | 性能指标 | 成本口径 | 错误处理 |
|-------|------|-------------|-------------|------|-------------|-----------|----------|----------|----------|
| 1 清洗 | 非结构化 → 标准化 JSON + 质量分 | `CleaningInput` | `CleaningOutput` | parse_csv / parse_json / detect_duplicates / normalize_text / extract_timestamp | 0.0 | 60s / 3 次 | 准确率 > 95%，吞吐 ≥ 1000 条/分钟（批处理） | 按实际模型单价重算 | `CleaningError` / `ParseError` / `CleaningValidationError` |
| 2 评估 | 5 维质量评估 | `EvaluationInput` | `EvaluationOutput` | search_knowledge_base / detect_hallucination / analyze_sentiment / check_compliance | 0.0 | 60s / 3 次 | 准确率 > 85%，召回率 > 90%，< 2s/条 | 按实际模型单价重算 | `EvaluationError` / `AgentOutputError` |
| 3 提取 | 对话 → FAQ + 知识盲区 | `ExtractionInput` | `ExtractionOutput` | extract_questions / cluster_similar_questions / extract_standard_answer / categorize_faq / generate_embedding | 0.0 | 60s / 3 次 | 提取准确率 > 80%，100 条/分钟 | 按实际模型单价重算 | `ExtractionError` / `AgentOutputError` |
| 4 洞察 | 诉求 / 情感 / 痛点 / 趋势 | `InsightInput` | `InsightOutput` | classify_intent / analyze_sentiment / identify_pain_points / detect_trends | 0.3 | 120s / 3 次 | 意图 > 85%，情感 > 80%，< 5s/100 条 | 按实际模型单价重算 | `InsightError` / 降级为 `None` |
| 5 报告 | 生成 4 类报告 | `ReportInput` | `ReportOutput` | render_markdown / export_pdf / export_excel / upload_to_minio | 0.3 | 120s / 3 次 | 渲染成功率 > 99%，Markdown < 2s | 按实际模型单价重算 | `ReportError` / `AgentOutputError` |

> 说明：`temperature` 默认 0.0（`settings.DEFAULT_TEMPERATURE`，结构化输出），仅洞察/报告类覆盖为 0.3；模型统一 `ChatDeepSeek(model=settings.DEFAULT_LLM_MODEL, ...)`，不写死模型 id。

---

## 📊 Agent 开发清单

开发新 Agent 时，确保完成：

- [ ] 定义 Input/Output Schema
- [ ] 实现 BaseAgent 的所有抽象方法
- [ ] 实现必要的工具（Tools）
- [ ] 编写 Prompt（system.txt + examples.json，2-3 条示例）
- [ ] 实现输入/输出验证
- [ ] 添加错误处理（继承 `AgentError` 体系）和重试逻辑（`max_retries` + 指数退避）
- [ ] 编写单元测试（> 80% 覆盖）
- [ ] 编写 Prompt 测试（每维度 ≥10 用例，合计 ≥50 用例）
- [ ] 性能测试（Token/成本/速度）
- [ ] 编写 README 文档
- [ ] 记录版本号（version.txt）

---

**Agent 设计完成！准备开始实现！** 🚀
