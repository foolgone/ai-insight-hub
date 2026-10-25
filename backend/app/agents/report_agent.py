"""报告生成 Agent（B-508；Agent 详细设计 §5）。

- 4 类报告：quality / knowledge / insight / comprehensive；
- 输出结构化 sections/summary/highlights/recommendations；
- ``generated_at`` 由 Agent 生成（不信任 LLM；对齐 ``reports.created_at`` 口径）；
- 洞察数据缺失时降级：sections 明确写「暂无洞察数据」，不阻塞报告生成；
- Markdown/Excel 渲染与落库由 ``report_service`` 负责（模板一一对应，B-510）。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.agents.base import (
    AgentConfig,
    AgentInputError,
    AgentOutputError,
    BaseAgent,
)
from app.schemas.agents.report import (
    REPORT_TYPE_LABELS,
    ReportInput,
    ReportLLMOutput,
    ReportOutput,
)

PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts" / "reports"
INSIGHT_MISSING_NOTICE = "暂无洞察数据：本报告未包含洞察分析结果（数据库为空或洞察任务未完成）"

_TYPE_INSTRUCTIONS: dict[str, str] = {
    "quality": "聚焦质量评估：总分/五维均分/需复核数量/低分维度，并给出改进建议。",
    "knowledge": "聚焦知识库：知识总量、种子/提取/手动来源占比、冷启动阶段、知识盲区。",
    "insight": "聚焦洞察：主要客诉主题、趋势、机会与风险（数据不足时明确说明）。",
    "comprehensive": "综合质量、知识库与洞察三部分，先总览再分项，最后给出优先级建议。",
}


class ReportGenerationAgent(BaseAgent):
    """按报告类型生成结构化报告内容。"""

    output_schema = ReportLLMOutput

    def __init__(self, config: AgentConfig | None = None, *, llm: Any = None) -> None:
        super().__init__(
            config or AgentConfig(name="report_agent", temperature=0.3),
            llm=llm,
        )
        self._active_input: ReportInput | None = None

    # -- BaseAgent hooks ---------------------------------------------------
    def _init_tools(self) -> None:
        self.tools = {}

    def _load_prompt(self) -> str:
        if self._prompt is None:
            self._prompt = (PROMPT_DIR / "system.txt").read_text(encoding="utf-8")
        return self._prompt

    def _create_agent(self, input_data: Any) -> list[dict[str, str]]:
        payload = ReportInput.model_validate(dict(input_data))
        self._active_input = payload
        system_prompt = (
            f"{self._load_prompt()}\n\n"
            f"## 本次报告类型：{REPORT_TYPE_LABELS[payload.report_type]}\n"
            f"{_TYPE_INSTRUCTIONS[payload.report_type]}"
        )
        user_content = {
            "title": payload.title,
            "report_type": payload.report_type,
            "time_range": payload.config.time_range,
            "data": payload.data,
        }
        return [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": json.dumps(user_content, ensure_ascii=False),
            },
        ]

    def _validate_input(self, input_data: Any) -> None:
        try:
            payload = ReportInput.model_validate(dict(input_data))
        except Exception as exc:  # noqa: BLE001
            raise AgentInputError(f"invalid report input: {exc}") from exc
        if not payload.data:
            raise AgentInputError("report data must not be empty")

    def _validate_output(self, data: Any) -> dict[str, Any]:
        if isinstance(data, ReportLLMOutput):
            llm_output = data
        else:
            try:
                llm_output = ReportLLMOutput.model_validate(data)
            except Exception as exc:  # noqa: BLE001
                raise AgentOutputError(f"invalid report output: {exc}") from exc
        if not llm_output.sections:
            raise AgentOutputError("report must contain at least one section")

        payload = self._active_input
        if payload is None:
            raise AgentOutputError("report input missing")

        insight_missing = payload.data.get("insight") in (None, {}, [])
        recommendations = (
            list(llm_output.recommendations) if payload.config.include_recommendations else []
        )
        output = ReportOutput(
            title=payload.title,
            report_type=payload.report_type,
            generated_at=datetime.now(timezone.utc).replace(tzinfo=None),
            summary=llm_output.summary,
            sections=llm_output.sections,
            highlights=list(llm_output.highlights),
            recommendations=recommendations,
            metadata={
                "insight_degraded": bool(
                    insight_missing and payload.report_type in ("insight", "comprehensive")
                ),
                "data_keys": sorted(payload.data),
                "include_charts": payload.config.include_charts,
            },
        )
        return output.model_dump(mode="json")

    # -- 便捷入口 ---------------------------------------------------------
    async def generate(self, input_data: Any, **kwargs: Any):
        return await self.invoke(input_data, **kwargs)


__all__ = [
    "INSIGHT_MISSING_NOTICE",
    "PROMPT_DIR",
    "ReportGenerationAgent",
]
