"""洞察分析 Agent（B-601；Agent 详细设计 §5）。

- 输出：诉求分布（条数）/ 高频问题 / 情感分布（0-1 且和=1）/ 趋势 / 痛点 / 未解决 / 新兴话题；
- 降级三分支：
  1) 情感分析失败 → ``sentiment_distribution`` 置空 + ``degraded=True``，其余维度照常；
  2) 趋势数据不足 → ``sentiment_trend=[]``，不视为错误；
  3) 整节点失败 → 由编排器跳过洞察，报告标注「洞察分析缺失」。
- 温度 0.3、超时 120s（Agent 设计允许覆盖全局默认）。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.agents.base import (
    AgentConfig,
    AgentInputError,
    AgentOutputError,
    BaseAgent,
)
from app.schemas.agents.insight import (
    SENTIMENT_LABELS,
    InsightInput,
    InsightLLMOutput,
    InsightOutput,
    TopQuestion,
)

PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts" / "insight"
TASK_DIR = PROMPT_DIR / "tasks"
DIALOGUE_LIMIT = 100
FEW_SHOT_LIMIT = 1


def _normalize_sentiment(raw: dict[str, float]) -> dict[str, float]:
    """归一化情感占比：过滤标签、裁剪负数、和强制为 1.0（保留 4 位小数）。"""
    values: dict[str, float] = {}
    for label in SENTIMENT_LABELS:
        if label in raw:
            values[label] = max(0.0, float(raw[label]))
    total = sum(values.values())
    if total <= 0:
        return {}
    normalized = {label: round(value / total, 4) for label, value in values.items()}
    difference = round(1.0 - sum(normalized.values()), 4)
    if difference:
        target = "中性" if "中性" in normalized else next(iter(normalized))
        normalized[target] = round(normalized[target] + difference, 4)
    return normalized


class InsightAnalysisAgent(BaseAgent):
    """批量对话的洞察分析 Agent。"""

    output_schema = InsightLLMOutput

    def __init__(self, config: AgentConfig | None = None, *, llm: Any = None) -> None:
        super().__init__(
            config
            or AgentConfig(
                name="insight_agent",
                temperature=0.3,
                timeout=120,
                max_tokens=4096,
            ),
            llm=llm,
        )
        self._active_input: InsightInput | None = None
        self._examples: list[dict[str, Any]] | None = None

    # -- BaseAgent hooks ---------------------------------------------------
    def _init_tools(self) -> None:
        self.tools = {}

    def _load_prompt(self) -> str:
        if self._prompt is None:
            sections = [
                (PROMPT_DIR / "system.txt").read_text(encoding="utf-8"),
                "## 任务说明",
            ]
            for name in (
                "intent_classification",
                "sentiment_analysis",
                "pain_point_detection",
                "trend_analysis",
            ):
                path = TASK_DIR / f"{name}.txt"
                if path.is_file():
                    sections.append(path.read_text(encoding="utf-8").strip())
            self._prompt = "\n\n".join(sections)
        return self._prompt

    def _load_examples(self) -> list[dict[str, Any]]:
        if self._examples is None:
            self._examples = json.loads((PROMPT_DIR / "examples.json").read_text(encoding="utf-8"))
        return self._examples

    def _create_agent(self, input_data: Any) -> list[dict[str, str]]:
        payload = InsightInput.model_validate(dict(input_data))
        self._active_input = payload
        messages: list[dict[str, str]] = [{"role": "system", "content": self._load_prompt()}]
        for example in self._load_examples()[:FEW_SHOT_LIMIT]:
            messages.append(
                {
                    "role": "user",
                    "content": json.dumps({"input": example["input"]}, ensure_ascii=False),
                }
            )
            messages.append(
                {
                    "role": "assistant",
                    "content": json.dumps(example["output"], ensure_ascii=False),
                }
            )
        dialogues = [
            {
                "dialogue_id": item.get("dialogue_id"),
                "timestamp": item.get("timestamp"),
                "user_message": item.get("user_message", ""),
                "ai_response": item.get("ai_response", ""),
            }
            for item in payload.dialogues[:DIALOGUE_LIMIT]
        ]
        messages.append(
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "datasource_id": str(payload.datasource_id),
                        "time_range": payload.time_range,
                        "dialogues": dialogues,
                    },
                    ensure_ascii=False,
                ),
            }
        )
        return messages

    def _validate_input(self, input_data: Any) -> None:
        try:
            payload = InsightInput.model_validate(dict(input_data))
        except Exception as exc:  # noqa: BLE001
            raise AgentInputError(f"invalid insight input: {exc}") from exc
        if not payload.dialogues:
            raise AgentInputError("dialogues must not be empty")

    def _validate_output(self, data: Any) -> dict[str, Any]:
        if isinstance(data, InsightLLMOutput):
            llm_output = data
        else:
            try:
                llm_output = InsightLLMOutput.model_validate(data)
            except Exception as exc:  # noqa: BLE001
                raise AgentOutputError(f"invalid insight output: {exc}") from exc

        payload = self._active_input
        if payload is None:
            raise AgentOutputError("insight input missing")
        config = payload.config

        intent_distribution = {
            str(key): max(0, int(value))
            for key, value in llm_output.intent_distribution.items()
            if int(value) > 0
        }
        top_questions = [
            TopQuestion(
                question=item.question,
                count=max(0, item.count),
                ratio=round(min(1.0, max(0.0, float(item.ratio))), 4),
            )
            for item in llm_output.top_questions
        ]

        degraded = False
        sentiment: dict[str, float] = {}
        if config.analyze_sentiment:
            sentiment = _normalize_sentiment(llm_output.sentiment_distribution)
            if not sentiment:
                degraded = True

        trend = list(llm_output.sentiment_trend) if config.identify_trends else []
        pain_points = list(llm_output.pain_points) if config.find_pain_points else []

        output = InsightOutput(
            datasource_id=payload.datasource_id,
            intent_distribution=intent_distribution,
            top_questions=top_questions,
            sentiment_distribution=sentiment,
            sentiment_trend=trend,
            pain_points=pain_points,
            unresolved_issues=list(llm_output.unresolved_issues),
            emerging_topics=list(llm_output.emerging_topics),
            degraded=degraded,
            statistics={
                "dialogue_count": len(payload.dialogues),
                "intent_total": sum(intent_distribution.values()),
                "sentiment_sum": round(sum(sentiment.values()), 4),
            },
        )
        return output.model_dump(mode="json")

    # -- 便捷入口 ---------------------------------------------------------
    async def analyze(self, input_data: Any, **kwargs: Any):
        return await self.invoke(input_data, **kwargs)


__all__ = [
    "DIALOGUE_LIMIT",
    "PROMPT_DIR",
    "InsightAnalysisAgent",
]
