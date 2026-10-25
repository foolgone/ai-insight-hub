"""数据清洗 Agent（B-313；Agent 详细设计 §2）。

- 输入：``CleaningInput``（datasource_id / raw_data / data_type / config）；
- 输出：``CleaningOutput``（dialogues + 统计；计数由 Agent 重算保证一致）；
- 工具：``app.agents.tools.cleaning_tools`` 的 5 个纯函数（parse/dedup/normalize/timestamp）；
- 质量分固定 0-100；结构化输出失败由 BaseAgent 内置兜底（一次修复）。
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
from app.agents.tools import cleaning_tools
from app.schemas.agents.cleaning import (
    CleaningInput,
    CleaningOutput,
    CleaningState,
)

PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts" / "cleaning"
FEW_SHOT_LIMIT = 2

STATE_SEQUENCE: tuple[CleaningState, ...] = (
    CleaningState.PENDING,
    CleaningState.PARSING,
    CleaningState.DEDUPLICATING,
    CleaningState.NORMALIZING,
    CleaningState.VALIDATING,
    CleaningState.COMPLETED,
)


class DataCleaningAgent(BaseAgent):
    """客服对话数据清洗 Agent。"""

    output_schema = CleaningOutput

    def __init__(self, config: AgentConfig | None = None, *, llm: Any = None) -> None:
        super().__init__(config or AgentConfig(name="cleaning_agent"), llm=llm)
        self._examples: list[dict[str, Any]] | None = None

    # -- BaseAgent hooks ---------------------------------------------------
    def _init_tools(self) -> None:
        self.tools = {
            "parse_csv": cleaning_tools.parse_csv,
            "parse_json": cleaning_tools.parse_json,
            "detect_duplicates": cleaning_tools.detect_duplicates,
            "normalize_text": cleaning_tools.normalize_text,
            "extract_timestamp": cleaning_tools.extract_timestamp,
        }

    def _load_prompt(self) -> str:
        if self._prompt is None:
            self._prompt = (PROMPT_DIR / "system.txt").read_text(encoding="utf-8")
        return self._prompt

    def _load_examples(self) -> list[dict[str, Any]]:
        if self._examples is None:
            self._examples = json.loads((PROMPT_DIR / "examples.json").read_text(encoding="utf-8"))
        return self._examples

    def _create_agent(self, input_data: Any) -> list[dict[str, str]]:
        payload = CleaningInput.model_validate(dict(input_data))
        raw_text = payload.raw_data
        if payload.config.normalize_text:
            raw_text = cleaning_tools.normalize_text(raw_text)

        messages: list[dict[str, str]] = [{"role": "system", "content": self._load_prompt()}]
        for example in self._load_examples()[:FEW_SHOT_LIMIT]:
            messages.append(
                {
                    "role": "user",
                    "content": json.dumps(example["input"], ensure_ascii=False),
                }
            )
            messages.append(
                {
                    "role": "assistant",
                    "content": json.dumps(
                        {"dialogues": example["output"]["dialogues"]},
                        ensure_ascii=False,
                    ),
                }
            )
        messages.append(
            {
                "role": "user",
                "content": (
                    f"datasource_id: {payload.datasource_id}\n"
                    f"data_type: {payload.data_type}\n\n"
                    f"{raw_text}"
                ),
            }
        )
        return messages

    def _validate_input(self, input_data: Any) -> None:
        try:
            payload = CleaningInput.model_validate(dict(input_data))
        except Exception as exc:  # noqa: BLE001 - pydantic 校验错误统一转换
            raise AgentInputError(f"invalid cleaning input: {exc}") from exc
        if not payload.raw_data.strip():
            raise AgentInputError("raw_data must not be empty")

    def _validate_output(self, data: Any) -> dict[str, Any]:
        if isinstance(data, CleaningOutput):
            output = data
        else:
            try:
                output = CleaningOutput.model_validate(data)
            except Exception as exc:  # noqa: BLE001
                raise AgentOutputError(f"invalid cleaning output: {exc}") from exc

        dialogues = output.dialogues
        if not dialogues:
            raise AgentOutputError("cleaning output contains no dialogues")

        cleaned_records = len(dialogues)
        total_records = max(output.total_records, cleaned_records)
        failed_records = max(0, total_records - cleaned_records)
        avg_quality = round(sum(item.quality_score for item in dialogues) / cleaned_records, 2)

        payload = output.model_dump(mode="json")
        payload.update(
            {
                "total_records": total_records,
                "cleaned_records": cleaned_records,
                "failed_records": failed_records,
            }
        )
        payload["statistics"].update(
            {
                "total_records": total_records,
                "cleaned_records": cleaned_records,
                "failed_records": failed_records,
                "avg_quality_score": avg_quality,
            }
        )
        return payload

    # -- 便捷入口 ---------------------------------------------------------
    async def clean(self, input_data: Any, **kwargs: Any):
        """执行清洗（等价于 ``invoke``）。"""
        return await self.invoke(input_data, **kwargs)


__all__ = [
    "FEW_SHOT_LIMIT",
    "PROMPT_DIR",
    "STATE_SEQUENCE",
    "DataCleaningAgent",
]
