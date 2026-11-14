"""RAG Judge Agent（Phase 3B）。

一个 Agent 覆盖三个指标，按 ``metric`` 切换 Prompt 与输出 Schema：
- ``faithfulness``：claim 拆分 + 支持性判断（**总分由代码算**，模型不自报）；
- ``answer_correctness``：与金标比对（score/missing/wrong/reason）；
- ``answer_relevancy``：是否回应问题（不掺入事实正确性）。

复用 ``BaseAgent`` 的重试/超时/降级/结构化输出与一次修复；
``AgentResult.raw_text`` 记录**最终实际用于解析**的模型输出（含修复轮），供追溯。
"""
from __future__ import annotations

import hashlib
import json
import math
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import (
    AgentConfig,
    AgentInputError,
    AgentOutputError,
    AgentResult,
    BaseAgent,
    load_prompt_version,
)
from app.core.config import settings
from app.schemas.agents.rag_judge import (
    METRIC_OUTPUT_SCHEMAS,
    RAG_JUDGE_METRIC_VERSION,
    RagJudgeInput,
    RagJudgeMetric,
)

PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts" / "rag_judge"


class RagJudgeAgent(BaseAgent):
    """按 metric 参数化的 Judge Agent。"""

    def __init__(
        self,
        metric: RagJudgeMetric,
        *,
        config: AgentConfig | None = None,
        llm: Any = None,
        credentials: Any = None,
    ) -> None:
        if metric not in METRIC_OUTPUT_SCHEMAS:
            raise ValueError(f"unsupported rag judge metric: {metric}")
        self.metric: RagJudgeMetric = metric
        self._active_input: RagJudgeInput | None = None
        super().__init__(
            config
            or AgentConfig(
                name=f"rag_judge_{metric}",
                version=load_prompt_version(PROMPT_DIR),
                # Judge 输出含 claim 明细，推理模型还会占 reasoning token
                max_tokens=settings.RAG_JUDGE_MAX_TOKENS,
            ),
            llm=llm,
            credentials=credentials,
        )
        self.output_schema = METRIC_OUTPUT_SCHEMAS[metric]

    # ------------------------------------------------------------------ 元信息

    @property
    def metric_version(self) -> str:
        return RAG_JUDGE_METRIC_VERSION[self.metric]

    @property
    def prompt_sha256(self) -> str:
        return hashlib.sha256(self._load_prompt().encode("utf-8")).hexdigest()

    # ------------------------------------------------------------------ BaseAgent hooks

    def _init_tools(self) -> None:
        self.tools = {}

    def _load_prompt(self) -> str:
        if self._prompt is None:
            self._prompt = (PROMPT_DIR / f"{self.metric}.txt").read_text(encoding="utf-8")
        return self._prompt

    def _create_agent(self, input_data: Any) -> list[dict[str, str]]:
        payload = RagJudgeInput.model_validate(dict(input_data))
        self._active_input = payload

        user_payload: dict[str, Any] = {"query": payload.query}
        if self.metric == "faithfulness":
            user_payload["answer"] = payload.answer
            user_payload["contexts"] = payload.contexts
        elif self.metric == "answer_correctness":
            user_payload["answer"] = payload.answer
            user_payload["gold_answer"] = payload.gold_answer
        else:
            user_payload["answer"] = payload.answer

        return [
            {"role": "system", "content": self._load_prompt()},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ]

    def _validate_input(self, input_data: Any) -> None:
        try:
            payload = RagJudgeInput.model_validate(dict(input_data))
        except Exception as exc:  # noqa: BLE001 - 统一转输入错误
            raise AgentInputError(f"invalid rag judge input: {exc}") from exc

        answer = (payload.answer or "").strip()
        if self.metric == "faithfulness":
            if not answer:
                raise AgentInputError("answer is required for faithfulness")
            if not payload.contexts:
                raise AgentInputError("contexts are required for faithfulness")
        elif self.metric == "answer_correctness":
            if not answer:
                raise AgentInputError("answer is required for answer_correctness")
            if not (payload.gold_answer or "").strip():
                raise AgentInputError("gold_answer is required for answer_correctness")
        else:
            if not answer:
                raise AgentInputError("answer is required for answer_relevancy")

    def _validate_output(self, data: Any) -> dict[str, Any]:
        schema = METRIC_OUTPUT_SCHEMAS[self.metric]
        if isinstance(data, schema):
            parsed = data
        else:
            try:
                parsed = schema.model_validate(data)
            except Exception as exc:  # noqa: BLE001
                raise AgentOutputError(f"invalid rag judge output: {exc}") from exc
        return parsed.model_dump(mode="json")

    def _validate_parsed(self, model: Any) -> None:
        """业务校验：分数必须是有限且在 [0,1] 内（schema 之外再兜一层）。"""
        score = getattr(model, "score", None)
        if score is None:
            return
        value = float(score)
        if not math.isfinite(value) or value < 0 or value > 1:
            raise ValueError("score must be a finite number within [0, 1]")

    # ------------------------------------------------------------------ 便捷入口

    async def judge(
        self,
        input_data: Any,
        *,
        session: AsyncSession | None = None,
        task_id: uuid.UUID | str | None = None,
        scope: str | None = None,
        user_id: uuid.UUID | None = None,
        datasource_id: uuid.UUID | None = None,
    ) -> AgentResult:
        """执行一次 Judge（等价于 ``invoke``）。"""
        return await self.invoke(
            input_data,
            session=session,
            task_id=task_id,
            scope=scope,
            user_id=user_id,
            datasource_id=datasource_id,
        )


__all__ = ["PROMPT_DIR", "RagJudgeAgent"]
