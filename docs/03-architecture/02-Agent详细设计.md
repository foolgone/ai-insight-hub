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
┌─────────────────────────────────────────────────┐
│              Orchestrator Layer                 │
│         (LangGraph Workflow Manager)            │
└──────────────┬──────────────────────────────────┘
               │
               ↓
┌─────────────────────────────────────────────────┐
│              Agent Layer                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐     │
│  │Cleaning  │  │Evaluation│  │Extraction│     │
│  │ Agent    │→ │  Agent   │→ │  Agent   │     │
│  └──────────┘  └──────────┘  └──────────┘     │
│                      ↓                          │
│               ┌──────────┐                      │
│               │ Report   │                      │
│               │ Agent    │                      │
│               └──────────┘                      │
└─────────────────────────────────────────────────┘
               ↓
┌─────────────────────────────────────────────────┐
│              Tools Layer                        │
│  Parser | Validator | Database | File I/O      │
└─────────────────────────────────────────────────┘
```

---

### 1.2 Agent 统一接口

**BaseAgent 抽象类**：

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from langchain.agents import AgentExecutor

class AgentConfig(BaseModel):
    """Agent 配置"""
    name: str
    version: str
    model: str = "claude-3-5-sonnet-20250219"
    temperature: float = 0.3
    max_tokens: int = 4096
    timeout: int = 60  # 秒
    max_retries: int = 3

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
    cost: float  # 美元

class BaseAgent(ABC):
    """所有 Agent 的基类"""
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.llm = self._init_llm()
        self.tools = self._init_tools()
        self.prompt = self._load_prompt()
        self.agent = self._create_agent()
    
    @abstractmethod
    def _init_tools(self) -> List[Any]:
        """初始化工具（子类实现）"""
        pass
    
    @abstractmethod
    def _load_prompt(self) -> Any:
        """加载 Prompt（子类实现）"""
        pass
    
    @abstractmethod
    def _create_agent(self) -> AgentExecutor:
        """创建 Agent（子类实现）"""
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
        """执行 Agent（统一入口）"""
        import time
        
        # 1. 输入验证
        if not self._validate_input(input_data):
            return AgentResult(
                success=False,
                data={},
                metadata={},
                errors=["输入验证失败"],
                duration=0,
                token_usage={},
                cost=0
            )
        
        # 2. 执行
        start_time = time.time()
        try:
            result = self.agent.invoke(
                input_data,
                config={"callbacks": callbacks or []}
            )
            duration = time.time() - start_time
            
            # 3. 输出验证
            if not self._validate_output(result):
                return AgentResult(
                    success=False,
                    data=result,
                    metadata={"validation": "failed"},
                    errors=["输出验证失败"],
                    duration=duration,
                    token_usage=self._extract_token_usage(result),
                    cost=self._calculate_cost(result)
                )
            
            # 4. 返回
            return AgentResult(
                success=True,
                data=result,
                metadata=self._extract_metadata(result),
                duration=duration,
                token_usage=self._extract_token_usage(result),
                cost=self._calculate_cost(result)
            )
            
        except Exception as e:
            duration = time.time() - start_time
            return AgentResult(
                success=False,
                data={},
                metadata={"error": str(e)},
                errors=[str(e)],
                duration=duration,
                token_usage={},
                cost=0
            )
```

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
| **速度** | > 1000 条/分钟 | 处理速度 |
| **去重准确率** | > 90% | 正确识别重复的比例 |
| **Token 消耗** | < 500/条 | 平均 Token 使用 |
| **成本** | < $0.002/条 | 单条处理成本 |

---

#### 错误处理

```python
class CleaningError(Exception):
    """清洗错误基类"""
    pass

class ParseError(CleaningError):
    """解析错误"""
    pass

class ValidationError(CleaningError):
    """验证错误"""
    pass

# 错误处理策略
ERROR_HANDLING = {
    ParseError: "skip",        # 跳过该条，继续处理
    ValidationError: "retry",  # 重试 3 次
    Exception: "fail"          # 整体失败
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
    """计算加权总分"""
    
    total_score = 0
    for dim_name, score in dimension_scores.items():
        weight = DIMENSIONS[dim_name]["weight"]
        total_score += score * weight
    
    return round(total_score, 2)

def _classify_quality(self, score: float) -> str:
    """质量分级"""
    if score >= 90:
        return "excellent"
    elif score >= 75:
        return "good"
    elif score >= 60:
        return "acceptable"
    else:
        return "poor"
```

---

#### 性能指标

| 指标 | 目标 |
|------|------|
| **准确率** | > 85% |
| **召回率** | > 90%（问题检出率）|
| **速度** | < 2 秒/条 |
| **Token 消耗** | < 800/条 |
| **成本** | < $0.003/条 |

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
    
    # 生成嵌入
    model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    embeddings = model.encode(questions)
    
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
    
    return self.llm.invoke(prompt)
```

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
| **知识盲区覆盖率** | > 85% |
| **处理速度** | 100 条对话/分钟 |
| **成本** | < $0.05/100 条 |

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
    
    # 诉求分析
    intent_distribution: Dict[str, int]  # {咨询: 45, 投诉: 30, ...}
    top_questions: List[dict]  # 高频问题
    
    # 情感分析
    sentiment_distribution: Dict[str, int]  # {正面: 40%, 中性: 50%, ...}
    sentiment_trend: List[dict]  # 时间序列
    
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

## 6. Agent 5: 报告生成 Agent

### 6.1 功能概述

**职责**：生成专业的分析报告

**输入**：所有分析结果
**输出**：PDF/Excel/Markdown 报告

---

### 6.2 详细设计

#### 输入 Schema

```python
class ReportInput(BaseModel):
    """报告生成输入"""
    datasource_id: str
    report_type: str  # quality/knowledge/insight/comprehensive
    data: dict  # 包含所有需要的数据
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
    generated_at: datetime
    metadata: dict
```

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

## 7. Agent 协作工作流

### 7.1 LangGraph 工作流

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict

class WorkflowState(TypedDict):
    """工作流状态"""
    datasource_id: str
    raw_data: str
    cleaned_data: List[dict]
    evaluation_results: List[dict]
    knowledge_base: List[dict]
    insights: dict
    report: dict
    status: str

# 创建工作流图
workflow = StateGraph(WorkflowState)

# 添加节点
workflow.add_node("clean", cleaning_agent.invoke)
workflow.add_node("evaluate", evaluation_agent.invoke)
workflow.add_node("extract", extraction_agent.invoke)
workflow.add_node("analyze", insight_agent.invoke)
workflow.add_node("report", report_agent.invoke)

# 定义流程
workflow.set_entry_point("clean")
workflow.add_edge("clean", "evaluate")
workflow.add_edge("evaluate", "extract")
workflow.add_edge("extract", "analyze")
workflow.add_edge("analyze", "report")
workflow.add_edge("report", END)

# 添加条件分支
def should_manual_review(state):
    """判断是否需要人工审核"""
    low_confidence = any(
        r["overall_score"] < 70
        for r in state["evaluation_results"]
    )
    if low_confidence:
        return "review"
    return "extract"

workflow.add_conditional_edges(
    "evaluate",
    should_manual_review,
    {
        "extract": "extract",
        "review": "manual_review"
    }
)

# 编译
app = workflow.compile()
```

---

### 7.2 数据流

```
原始数据 (CSV/TXT)
    ↓
[清洗 Agent] → 标准化 JSON
    ↓
[评估 Agent] → 质量评分 + 问题列表
    ↓
[提取 Agent] → FAQ + 知识盲区
    ↓
[分析 Agent] → 洞察报告
    ↓
[报告 Agent] → PDF/Excel 报告
```

---

## 8. 通用设计规范

### 8.1 命名规范

```python
# Agent 类命名
class DataCleaningAgent(BaseAgent):  # {功能}Agent

# 方法命名
def _init_tools(self):     # 私有方法用 _
def invoke(self, data):    # 公共方法不用 _
```

---

### 8.2 错误处理

```python
# 每个 Agent 都要实现
try:
    result = agent.invoke(data)
except AgentExecutionError as e:
    logger.error(f"Agent 执行失败: {e}")
    # 重试逻辑
except ValidationError as e:
    logger.error(f"验证失败: {e}")
    # 返回错误
except Exception as e:
    logger.critical(f"未知错误: {e}", exc_info=True)
    # 记录并报警
```

---

### 8.3 日志规范

```python
logger.info(f"[{agent_name}] 开始处理: {datasource_id}")
logger.debug(f"[{agent_name}] 输入数据: {input_data}")
logger.info(f"[{agent_name}] 处理完成: {result.success}")
logger.error(f"[{agent_name}] 处理失败: {error}")
```

---

### 8.4 测试要求

每个 Agent 必须有：
- ✅ 单元测试（覆盖率 > 80%）
- ✅ Prompt 测试（10+ 用例）
- ✅ 集成测试（完整流程）
- ✅ 性能测试（Token/成本）

---

## 📊 Agent 开发清单

开发新 Agent 时，确保完成：

- [ ] 定义 Input/Output Schema
- [ ] 实现 BaseAgent 的所有抽象方法
- [ ] 实现必要的工具（Tools）
- [ ] 编写 Prompt（system.txt + examples.json）
- [ ] 实现输入/输出验证
- [ ] 添加错误处理和重试逻辑
- [ ] 编写单元测试（> 80% 覆盖）
- [ ] 编写 Prompt 测试（10+ 用例）
- [ ] 性能测试（Token/成本/速度）
- [ ] 编写 README 文档
- [ ] 记录版本号（version.txt）

---

**Agent 设计完成！准备开始实现！** 🚀
