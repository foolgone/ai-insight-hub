"""转写文本结构化 Agent（内容路由）。

输入一段转写文本，输出 ``StructureOutput``：先判断 ``content_type``，
再决定用 ``qa`` / ``knowledge`` / ``summary`` 哪种形态承载。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import (
    AgentConfig,
    AgentInputError,
    AgentOutputError,
    AgentResult,
    BaseAgent,
    load_prompt_version,
)
from app.schemas.agents.structure import StructureInput, StructureOutput

PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts" / "structure"

# 单次结构化的文本上限（约 2 万汉字）。超过由调用方分块（structure_service），
# 这里只做兜底截断，避免误传超长文本把请求打爆。
MAX_TEXT_CHARS = 30000
# 结构化输出比其它 Agent 长（一组 QA 就要几十 token），全局 4096 会被截断；
# 实测 39 分钟面试需要 6000+ 输出 token，这里单独放宽到 8192。
STRUCTURE_MAX_TOKENS = 8192
# 输出更长 → 生成时间更长；60s 容易在长录音上超时
STRUCTURE_TIMEOUT = 120.0


class TranscriptStructureAgent(BaseAgent):
    """把未整理的转写文本结构化。"""

    output_schema = StructureOutput

    def __init__(
        self,
        config: AgentConfig | None = None,
        *,
        llm: Any = None,
        credentials: Any = None,
    ) -> None:
        super().__init__(
            config
            or AgentConfig(
                name="structure_agent",
                version=load_prompt_version(PROMPT_DIR),
                max_tokens=STRUCTURE_MAX_TOKENS,
                timeout=STRUCTURE_TIMEOUT,
            ),
            llm=llm,
            credentials=credentials,
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

    def _validate_parsed(self, model: Any) -> None:
        """业务校验（进入修复轮）：形态与内容必须自洽。"""
        if isinstance(model, StructureOutput):
            output = model
        else:  # pragma: no cover - parse_with_repair 只会传 schema 实例
            return
        if output.structure == "qa" and not output.qa:
            raise ValueError("structure=qa but qa is empty; 请从原文切出问答对，或改选其它 structure")
        if output.structure == "knowledge" and not output.knowledge:
            raise ValueError(
                "structure=knowledge but knowledge is empty; 请从原文提炼知识点，或改选其它 structure"
            )
        if output.structure == "summary" and not (output.summary or "").strip():
            raise ValueError(
                "structure=summary but summary is empty; 请用原文内容补全 summary，或改选 qa/knowledge"
            )

    def _validate_output(self, data: Any) -> dict[str, Any]:
        if isinstance(data, StructureOutput):
            output = data
        else:
            try:
                output = StructureOutput.model_validate(data)
            except Exception as exc:  # noqa: BLE001
                raise AgentOutputError(f"invalid structure output: {exc}") from exc

        # 修复轮之后仍然不自洽 → 判失败（不写库，由调用方降级）
        try:
            self._validate_parsed(output)
        except ValueError as exc:
            raise AgentOutputError(str(exc)) from exc
        return output.model_dump(mode="json")

    # -- 便捷入口 ---------------------------------------------------------
    async def structure(
        self,
        input_data: Any,
        *,
        session: AsyncSession | None = None,
        task_id: uuid.UUID | str | None = None,
        scope: str | None = None,
        user_id: uuid.UUID | None = None,
        datasource_id: uuid.UUID | None = None,
    ) -> AgentResult:
        """执行结构化（等价于 ``invoke``）。

        显式列出 ``invoke`` 的关键字参数，mypy 才能在调用点拦住不存在的参数；
        凭据走构造函数注入，不要再往这里传 ``credentials=``。
        """
        return await self.invoke(
            input_data,
            session=session,
            task_id=task_id,
            scope=scope,
            user_id=user_id,
            datasource_id=datasource_id,
        )


__all__ = [
    "MAX_TEXT_CHARS",
    "PROMPT_DIR",
    "STRUCTURE_MAX_TOKENS",
    "STRUCTURE_TIMEOUT",
    "TranscriptStructureAgent",
]
