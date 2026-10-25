"""知识提取 Agent（B-504；Agent 详细设计 §4）。

流程（Agent 侧）：输入清洗对话 → LLM 提取 FAQ/盲区 → 置信度过滤 + 问题去重 →
逐条计算 384 维 embedding（单条失败不阻塞整批，embedding 置 None 并告警）。

去重/落库策略由知识库服务执行（B-504：先删 ``is_seed`` 再插 ``extracted``）。
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
from app.schemas.agents.extraction import (
    MAX_DIALOGUES_PER_RUN,
    ExtractedFAQWithEmbedding,
    ExtractionInput,
    ExtractionLLMOutput,
    ExtractionOutput,
)
from app.services import embedding_service

PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts" / "extraction"
FEW_SHOT_LIMIT = 2


def _normalize_question(text: str) -> str:
    return " ".join((text or "").split()).strip().lower()


class KnowledgeExtractionAgent(BaseAgent):
    """从清洗对话中提取 FAQ / 知识盲区。"""

    output_schema = ExtractionLLMOutput

    def __init__(self, config: AgentConfig | None = None, *, llm: Any = None) -> None:
        super().__init__(config or AgentConfig(name="extraction_agent"), llm=llm)
        self._active_input: ExtractionInput | None = None
        self._examples: list[dict[str, Any]] | None = None

    # -- BaseAgent hooks ---------------------------------------------------
    def _init_tools(self) -> None:
        self.tools = {"embed": embedding_service.encode_texts_sync}

    def _load_prompt(self) -> str:
        if self._prompt is None:
            self._prompt = (PROMPT_DIR / "system.txt").read_text(encoding="utf-8")
        return self._prompt

    def _load_examples(self) -> list[dict[str, Any]]:
        if self._examples is None:
            self._examples = json.loads((PROMPT_DIR / "examples.json").read_text(encoding="utf-8"))
        return self._examples

    def _create_agent(self, input_data: Any) -> list[dict[str, str]]:
        payload = ExtractionInput.model_validate(dict(input_data))
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
        dialogues = payload.dialogues[:MAX_DIALOGUES_PER_RUN]
        compact = [
            {
                "dialogue_id": item.get("dialogue_id"),
                "user_message": item.get("user_message", ""),
                "ai_response": item.get("ai_response", ""),
            }
            for item in dialogues
        ]
        messages.append(
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "datasource_id": str(payload.datasource_id),
                        "existing_questions": payload.existing_questions[:30],
                        "dialogues": compact,
                    },
                    ensure_ascii=False,
                ),
            }
        )
        return messages

    def _validate_input(self, input_data: Any) -> None:
        try:
            payload = ExtractionInput.model_validate(dict(input_data))
        except Exception as exc:  # noqa: BLE001
            raise AgentInputError(f"invalid extraction input: {exc}") from exc
        if not payload.dialogues:
            raise AgentInputError("dialogues must not be empty")
        if not any(
            str(item.get("user_message", "")).strip() or str(item.get("ai_response", "")).strip()
            for item in payload.dialogues
            if isinstance(item, dict)
        ):
            raise AgentInputError("dialogues contain no usable messages")

    def _validate_output(self, data: Any) -> dict[str, Any]:
        if isinstance(data, ExtractionLLMOutput):
            llm_output = data
        else:
            try:
                llm_output = ExtractionLLMOutput.model_validate(data)
            except Exception as exc:  # noqa: BLE001
                raise AgentOutputError(f"invalid extraction output: {exc}") from exc

        payload = self._active_input
        if payload is None:
            raise AgentOutputError("extraction input missing")
        config = payload.config
        existing = {_normalize_question(question) for question in payload.existing_questions}

        faqs: list[ExtractedFAQWithEmbedding] = []
        seen: set[str] = set()
        filtered_confidence = 0
        duplicates_removed = 0
        embedding_failed = 0
        warnings: list[str] = []

        for faq in llm_output.faqs:
            if faq.confidence < config.min_confidence:
                filtered_confidence += 1
                continue
            key = _normalize_question(faq.question)
            if key in seen or key in existing:
                duplicates_removed += 1
                continue
            seen.add(key)
            faqs.append(ExtractedFAQWithEmbedding(**faq.model_dump()))
            if len(faqs) >= config.max_faqs:
                break

        for faq in faqs:
            text = faq.question
            if faq.variations:
                text = f"{text} {' '.join(faq.variations)}"
            try:
                faq.embedding = embedding_service.encode_texts_sync([text])[0]
            except Exception as exc:  # noqa: BLE001 - 单条失败不阻塞整批
                embedding_failed += 1
                warnings.append(f"embedding failed for {faq.question}: {exc}")
                faq.embedding = None

        gaps = list(llm_output.gaps) if config.include_gaps else []
        output = ExtractionOutput(
            datasource_id=payload.datasource_id,
            faqs=faqs,
            gaps=gaps,
            stats={
                "llm_faqs": len(llm_output.faqs),
                "kept": len(faqs),
                "filtered_low_confidence": filtered_confidence,
                "duplicates_removed": duplicates_removed,
                "embedding_failed": embedding_failed,
                "warnings": warnings,
            },
        )
        return output.model_dump(mode="json")

    # -- 便捷入口 ---------------------------------------------------------
    async def extract(self, input_data: Any, **kwargs: Any):
        return await self.invoke(input_data, **kwargs)


__all__ = ["KnowledgeExtractionAgent", "PROMPT_DIR"]
