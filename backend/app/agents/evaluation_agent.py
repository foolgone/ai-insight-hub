"""质量评估 Agent（B-401；Agent 详细设计 §3）。

- 5 维权重：0.35 / 0.25 / 0.20 / 0.10 / 0.10；
- 总分 = Σ(维度分×权重) / Σ(启用维度权重)（启用子集时自动归一化）；
- 阈值默认 70：总分 < 70 → ``needs_review=True``；
- 知识库为空时 hallucination 维度强制按 70 分保守计分并给出建议；
- 质量分级：≥90 excellent / ≥75 good / ≥60 fair / <60 poor。

Prompt 资产：``app/prompts/evaluation/``（system + 5 个维度说明 + version）。
"""
from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from app.agents.base import (
    AgentConfig,
    AgentInputError,
    AgentOutputError,
    BaseAgent,
)
from app.schemas.agents.evaluation import (
    DIMENSION_LABELS,
    DIMENSION_NAMES,
    DIMENSION_WEIGHTS,
    EMPTY_KNOWLEDGE_HALLUCINATION_SCORE,
    DimensionScore,
    EvaluationConfig,
    EvaluationInput,
    EvaluationLLMOutput,
    EvaluationOutput,
    QualityLevel,
)

PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts" / "evaluation"
DIMENSION_PROMPT_DIR = PROMPT_DIR / "dimensions"


def quality_level_for(score: float) -> QualityLevel:
    """按总分映射质量等级（与 Agent 设计 §3 一致）。"""
    if score >= 90:
        return QualityLevel.EXCELLENT
    if score >= 75:
        return QualityLevel.GOOD
    if score >= 60:
        return QualityLevel.FAIR
    return QualityLevel.POOR


def compute_overall_score(scores: dict[str, float], dimensions: Sequence[str]) -> float:
    """按启用维度权重归一化计算总分（保留 1 位小数）。"""
    total_weight = sum(DIMENSION_WEIGHTS[dim] for dim in dimensions)
    if total_weight <= 0:
        raise ValueError("no enabled dimensions")
    weighted = sum(scores[dim] * DIMENSION_WEIGHTS[dim] for dim in dimensions)
    return round(weighted / total_weight, 1)


class QualityEvaluationAgent(BaseAgent):
    """单条对话的 5 维质量评估 Agent。"""

    output_schema = EvaluationLLMOutput

    def __init__(self, config: AgentConfig | None = None, *, llm: Any = None) -> None:
        super().__init__(config or AgentConfig(name="evaluation_agent"), llm=llm)
        self._active_input: EvaluationInput | None = None

    # -- BaseAgent hooks ---------------------------------------------------
    def _init_tools(self) -> None:
        self.tools = {}

    def _load_prompt(self) -> str:
        if self._prompt is None:
            sections = [
                (PROMPT_DIR / "system.txt").read_text(encoding="utf-8"),
                "## 维度说明",
            ]
            for dimension in DIMENSION_NAMES:
                path = DIMENSION_PROMPT_DIR / f"{dimension}.txt"
                if path.is_file():
                    sections.append(
                        f"### {DIMENSION_LABELS[dimension]}（{dimension}）\n"
                        f"{path.read_text(encoding='utf-8').strip()}"
                    )
            self._prompt = "\n\n".join(sections)
        return self._prompt

    def _create_agent(self, input_data: Any) -> list[dict[str, str]]:
        payload = EvaluationInput.model_validate(dict(input_data))
        self._active_input = payload
        dialogue = payload.dialogue
        user_payload = {
            "dialogue": {
                "dialogue_id": dialogue.get("dialogue_id"),
                "timestamp": dialogue.get("timestamp"),
                "user_message": dialogue.get("user_message", ""),
                "ai_response": dialogue.get("ai_response", ""),
            },
            "knowledge_base": payload.knowledge_base[:5],
            "dimensions": payload.config.dimensions,
        }
        return [
            {"role": "system", "content": self._load_prompt()},
            {
                "role": "user",
                "content": json.dumps(user_payload, ensure_ascii=False),
            },
        ]

    def _validate_input(self, input_data: Any) -> None:
        try:
            payload = EvaluationInput.model_validate(dict(input_data))
        except Exception as exc:  # noqa: BLE001
            raise AgentInputError(f"invalid evaluation input: {exc}") from exc
        dialogue = payload.dialogue
        if not isinstance(dialogue, dict):
            raise AgentInputError("dialogue must be a dict")
        user_message = str(dialogue.get("user_message", "")).strip()
        ai_response = str(dialogue.get("ai_response", "")).strip()
        if not user_message and not ai_response:
            raise AgentInputError("dialogue has neither user_message nor ai_response")

    def _validate_output(self, data: Any) -> dict[str, Any]:
        if isinstance(data, EvaluationLLMOutput):
            llm_output = data
        else:
            try:
                llm_output = EvaluationLLMOutput.model_validate(data)
            except Exception as exc:  # noqa: BLE001
                raise AgentOutputError(f"invalid evaluation output: {exc}") from exc

        payload = self._active_input
        config = payload.config if payload is not None else EvaluationConfig()
        dialogue = payload.dialogue if payload is not None else {}
        knowledge_base = payload.knowledge_base if payload is not None else []
        enabled = list(config.dimensions)

        scores: dict[str, float] = {}
        dimension_payload: dict[str, dict[str, Any]] = {}
        for dimension in enabled:
            scored = llm_output.dimensions.get(dimension)
            if scored is None:
                raise AgentOutputError(f"missing evaluation dimension: {dimension}")
            scores[dimension] = float(scored.score)
            dimension_payload[dimension] = scored.model_dump()

        suggestions = list(llm_output.suggestions)

        if not knowledge_base and "hallucination" in scores:
            scores["hallucination"] = EMPTY_KNOWLEDGE_HALLUCINATION_SCORE
            hallucination = dimension_payload["hallucination"]
            hallucination["score"] = EMPTY_KNOWLEDGE_HALLUCINATION_SCORE
            issues = list(hallucination.get("issues") or [])
            if "knowledge_base_empty" not in issues:
                issues.append("knowledge_base_empty")
            hallucination["issues"] = issues
            suggestions.append("知识库为空，幻觉检测按 70 分保守计分")

        overall_score = compute_overall_score(scores, enabled)

        critical_issues: list[str] = []
        minor_issues: list[str] = []
        for dimension in enabled:
            score = scores[dimension]
            issues = list(dimension_payload[dimension].get("issues") or [])
            if score < 60:
                critical_issues.append(f"{dimension}: critical low score {score}")
                critical_issues.extend(f"{dimension}: {issue}" for issue in issues)
            elif score < config.threshold:
                minor_issues.append(f"{dimension}: below threshold {score}")
                minor_issues.extend(f"{dimension}: {issue}" for issue in issues)

        has_issues = bool(critical_issues or minor_issues) or any(
            dimension_payload[dimension].get("issues") for dimension in enabled
        )

        output = EvaluationOutput(
            dialogue_id=str(dialogue.get("dialogue_id") or "unknown"),
            overall_score=overall_score,
            dimensions={
                dimension: DimensionScore.model_validate(dimension_payload[dimension])
                for dimension in enabled
            },
            has_issues=has_issues,
            critical_issues=critical_issues,
            minor_issues=minor_issues,
            suggestions=suggestions,
            quality_level=quality_level_for(overall_score),
            needs_review=overall_score < config.threshold,
        )
        return output.model_dump(mode="json")

    # -- 便捷入口 ---------------------------------------------------------
    async def evaluate(self, input_data: Any, **kwargs: Any):
        return await self.invoke(input_data, **kwargs)


__all__ = [
    "DIMENSION_PROMPT_DIR",
    "PROMPT_DIR",
    "QualityEvaluationAgent",
    "compute_overall_score",
    "quality_level_for",
]
