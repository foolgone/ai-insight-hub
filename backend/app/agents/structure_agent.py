"""转写文本结构化 Agent（内容路由）。

输入一段转写文本，输出 ``StructureOutput``：先判断 ``content_type``，
再决定用 ``qa`` / ``knowledge`` / ``summary`` 哪种形态承载。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from app.agents.base import (
    AgentConfig,
    AgentInputError,
    AgentOutputError,
    BaseAgent,
    load_prompt_version,
)
from app.schemas.agents.structure import StructureInput, StructureOutput

PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts" / "structure"

# 单次结构化的文本上限（约 2 万汉字），超出截断，避免 token 爆炸
MAX_TEXT_CHARS = 30000


class TranscriptStructureAgent(BaseAgent):
    """把未整理的转写文本结构化。"""

    output_schema = StructureOutput

    def __init__(self, config: AgentConfig | None = None, *, llm: Any = None) -> None:
        super().__init__(
            config or AgentConfig(name="structure_agent", version=load_prompt_version(PROMPT_DIR)),
            llm=llm,
        )

    # -- BaseAgent hooks ---------------------------------------------------
    def _init_tools(self) -> None:
        self.tools = {}

    def _load_prompt(self) -> str:
        if self._prompt is None:
            self._prompt = (PROMPT_DIR / "system.txt").read_text(encoding="utf-8")
        return self._prompt

    def _create_agent(self, input_data: Any) -> list[dict[str, str]]:
        payload = StructureInput.model_validate(dict(input_data))
        text = payload.text.strip()[:MAX_TEXT_CHARS]
        meta = (
            f"duration_seconds: {payload.duration}\n"
            f"channel_mode: {payload.channel_mode or 'unknown'}"
        )
        return [
            {"role": "system", "content": self._load_prompt()},
            {"role": "user", "content": f"{meta}\n\n{text}"},
        ]

    def _validate_input(self, input_data: Any) -> None:
        try:
            payload = StructureInput.model_validate(dict(input_data))
        except Exception as exc:  # noqa: BLE001 - pydantic 校验错误统一转换
            raise AgentInputError(f"invalid structure input: {exc}") from exc
        if not payload.text.strip():
            raise AgentInputError("text must not be empty")

    def _validate_output(self, data: Any) -> dict[str, Any]:
        if isinstance(data, StructureOutput):
            output = data
        else:
            try:
                output = StructureOutput.model_validate(data)
            except Exception as exc:  # noqa: BLE001
                raise AgentOutputError(f"invalid structure output: {exc}") from exc

        if output.structure == "qa" and not output.qa:
            raise AgentOutputError("structure=qa but qa is empty")
        if output.structure == "knowledge" and not output.knowledge:
            raise AgentOutputError("structure=knowledge but knowledge is empty")
        if output.structure == "summary" and not (output.summary or "").strip():
            raise AgentOutputError("structure=summary but summary is empty")
        return output.model_dump(mode="json")

    # -- 便捷入口 ---------------------------------------------------------
    async def structure(self, input_data: Any, **kwargs: Any):
        """执行结构化（等价于 ``invoke``）。"""
        return await self.invoke(input_data, **kwargs)


__all__ = ["MAX_TEXT_CHARS", "PROMPT_DIR", "TranscriptStructureAgent"]
