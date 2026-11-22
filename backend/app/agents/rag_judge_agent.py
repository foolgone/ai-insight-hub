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
import re
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
)
from app.core.config import settings
from app.schemas.agents.rag_judge import (
    JUDGE_SCHEMA_V2,
    JUDGE_SCHEMA_V3,
    METRIC_OUTPUT_SCHEMAS,
    RagJudgeInput,
    RagJudgeMetric,
    judge_schema_version,
    metric_version_for_prompt,
    output_schema_for,
)
from app.schemas.agents.rag_judge_evidence import (
    QuoteCheck,
    QuoteContractError,
    build_context_map,
    check_claims_evidence,
    detect_mixed_absence,
    format_quote_contract_error,
    quote_validator_sha256,
)

PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts" / "rag_judge"
PROMPT_VERSION_PATTERN = re.compile(r"^v\d+\.\d+\.\d+$")
CONTRACT_REPAIR_VERSION = "v1.2.3"


class RagJudgePromptError(RuntimeError):
    """Judge Prompt 制品缺失/损坏；不静默回退。"""


def resolve_prompt_version(explicit: str | None = None) -> str:
    """解析 Judge Prompt 版本；默认 v1.0.0，目录存在不会自动切换。"""
    value = (explicit or settings.RAG_JUDGE_PROMPT_VERSION or "v1.0.0").strip()
    return value or "v1.0.0"


def load_prompt_manifest(version: str, *, prompt_dir: Path = PROMPT_DIR) -> dict[str, Any]:
    """读取并校验 ``rag_judge/<version>/MANIFEST.json``。"""
    if not PROMPT_VERSION_PATTERN.match(version):
        raise RagJudgePromptError(f"invalid rag judge prompt version: {version!r}")
    manifest_path = prompt_dir / version / "MANIFEST.json"
    if not manifest_path.is_file():
        raise RagJudgePromptError(f"rag judge manifest missing: {manifest_path}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RagJudgePromptError(f"rag judge manifest unreadable: {manifest_path}") from exc
    if not isinstance(manifest, dict):
        raise RagJudgePromptError(f"rag judge manifest must be an object: {manifest_path}")
    if manifest.get("version") != version:
        raise RagJudgePromptError(
            f"rag judge manifest version mismatch: {manifest.get('version')!r} != {version!r}"
        )
    prompts = manifest.get("prompts")
    if not isinstance(prompts, dict) or not prompts:
        raise RagJudgePromptError(f"rag judge manifest has no prompts: {manifest_path}")
    return manifest


def load_judge_prompt(version: str, metric: str, *, prompt_dir: Path = PROMPT_DIR) -> str:
    """显式加载 ``<version>/<metric>.txt``，并按 MANIFEST 校验 SHA256。"""
    if metric not in METRIC_OUTPUT_SCHEMAS:
        raise RagJudgePromptError(f"unsupported rag judge metric: {metric!r}")
    manifest = load_prompt_manifest(version, prompt_dir=prompt_dir)
    filename = f"{metric}.txt"
    expected_sha = manifest["prompts"].get(filename)
    if not expected_sha:
        raise RagJudgePromptError(f"rag judge prompt not registered: {version}/{filename}")
    prompt_path = prompt_dir / version / filename
    if not prompt_path.is_file():
        raise RagJudgePromptError(f"rag judge prompt missing: {prompt_path}")
    try:
        text = prompt_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RagJudgePromptError(f"rag judge prompt unreadable: {prompt_path}") from exc
    actual_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if actual_sha != expected_sha:
        raise RagJudgePromptError(f"rag judge prompt sha256 mismatch: {version}/{filename}")
    return text


class RagJudgeAgent(BaseAgent):
    """按 metric 参数化的 Judge Agent。"""

    def __init__(
        self,
        metric: RagJudgeMetric,
        *,
        config: AgentConfig | None = None,
        llm: Any = None,
        credentials: Any = None,
        prompt_version: str | None = None,
    ) -> None:
        if metric not in METRIC_OUTPUT_SCHEMAS:
            raise ValueError(f"unsupported rag judge metric: {metric}")
        self.metric: RagJudgeMetric = metric
        self.prompt_version = resolve_prompt_version(prompt_version)
        manifest = load_prompt_manifest(self.prompt_version)
        expected_schema_version = judge_schema_version(self.prompt_version)
        manifest_schema_version = manifest.get("schema_version")
        if (
            manifest_schema_version is not None
            and manifest_schema_version != expected_schema_version
        ):
            raise RagJudgePromptError(
                "rag judge manifest schema_version mismatch: "
                f"{manifest_schema_version!r} != {expected_schema_version!r}"
            )
        self.schema_version = str(manifest_schema_version or expected_schema_version)
        self.rubric_version = str(manifest.get("rubric_version") or self.prompt_version)
        self.prompt_status = str(manifest.get("status") or "unknown")
        self.prompt_active = bool(manifest.get("active", False))
        self._active_input: RagJudgeInput | None = None
        self._contract_validation_attempts = 0
        self.contract_repair_version: str | None = None
        self.quote_validator_sha256: str | None = None
        self.contract_report: dict[str, Any] | None = None
        if self.prompt_version == CONTRACT_REPAIR_VERSION and metric == "faithfulness":
            self.contract_repair_version = CONTRACT_REPAIR_VERSION
            self.quote_validator_sha256 = quote_validator_sha256()
            self.contract_report = {
                "contract_version": CONTRACT_REPAIR_VERSION,
                "quote_validator_sha256": self.quote_validator_sha256,
                "quote_precheck_errors": [],
                "mixed_sentence_warnings": [],
                "repair_triggered": False,
                "repair_count": 0,
                "passed_after_repair": None,
                "final_errors": [],
            }
        super().__init__(
            config
            or AgentConfig(
                name=f"rag_judge_{metric}",
                version=self.prompt_version,
                # Judge 输出含 claim 明细，推理模型还会占 reasoning token
                max_tokens=settings.RAG_JUDGE_MAX_TOKENS,
            ),
            llm=llm,
            credentials=credentials,
        )
        self.output_schema = output_schema_for(metric, self.schema_version)

    # ------------------------------------------------------------------ 元信息

    @property
    def metric_version(self) -> str:
        return metric_version_for_prompt(self.metric, self.prompt_version)

    @property
    def prompt_sha256(self) -> str:
        return hashlib.sha256(self._load_prompt().encode("utf-8")).hexdigest()

    # ------------------------------------------------------------------ BaseAgent hooks

    def _init_tools(self) -> None:
        self.tools = {}

    def _load_prompt(self) -> str:
        if self._prompt is None:
            self._prompt = load_judge_prompt(self.prompt_version, self.metric)
        return self._prompt

    def _create_agent(self, input_data: Any) -> list[dict[str, str]]:
        payload = RagJudgeInput.model_validate(dict(input_data))
        self._active_input = payload

        user_payload: dict[str, Any] = {"query": payload.query}
        if self.metric == "faithfulness":
            user_payload["answer"] = payload.answer
            if self.schema_version in (JUDGE_SCHEMA_V2, JUDGE_SCHEMA_V3):
                # 显式给 context_id，避免模型把文档章节号（如 ## 7）当成 C7。
                user_payload["contexts"] = payload.contexts
                user_payload["context_ids"] = [
                    f"C{index}" for index in range(1, len(payload.contexts) + 1)
                ]
            else:
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
        schema = self.output_schema
        if schema is None:
            raise AgentOutputError("rag judge output schema is not configured")
        if isinstance(data, schema):
            parsed = data
        else:
            try:
                parsed = schema.model_validate(data)
            except Exception as exc:  # noqa: BLE001
                raise AgentOutputError(f"invalid rag judge output: {exc}") from exc
        return parsed.model_dump(mode="json")

    def _validate_parsed(self, model: Any) -> None:
        """业务校验：分数合法；v1.2.3 额外做 evidence quote 合同预校验。"""
        if self.contract_report is not None:
            self._validate_quote_contract(model)

        score = getattr(model, "score", None)
        if score is None:
            return
        value = float(score)
        if not math.isfinite(value) or value < 0 or value > 1:
            raise ValueError("score must be a finite number within [0, 1]")

    def _validate_quote_contract(self, model: Any) -> None:
        """v1.2.3-only：让 Agent 在 repair 前看到 quote 错误。"""
        assert self.contract_report is not None
        self._contract_validation_attempts += 1
        attempt = self._contract_validation_attempts
        claims = list(getattr(model, "claims", None) or [])

        contexts = list(self._active_input.contexts) if self._active_input else []
        context_map = build_context_map(contexts)
        if not context_map:
            self.contract_report["repair_triggered"] = True
            self.contract_report["repair_count"] = 1
            self.contract_report["final_errors"] = [
                {"code": "contexts_unavailable", "message": "contexts required for quote precheck"}
            ]
            raise QuoteContractError(
                "quote_contract_violation: contexts are unavailable; cannot verify "
                "evidence quotes. Provide contexts or do not mark evidence as supported."
            )
        checks = check_claims_evidence(claims, context_map)
        quote_errors = [check for check in checks if not check.ok]

        mixed_errors: list[dict[str, Any]] = []
        mixed_warnings: list[dict[str, Any]] = []
        for index, claim in enumerate(claims, 1):
            if getattr(claim, "claim_type", None) != "factual_claim":
                continue
            text = str(getattr(claim, "claim", "") or "")
            if not detect_mixed_absence(text):
                continue
            entry = {
                "claim_id": str(getattr(claim, "claim_id", None) or f"cl{index}"),
                "claim": text,
                "code": "mixed_sentence_factual_absence",
            }
            if getattr(claim, "support_status", None) == "supported":
                mixed_errors.append(entry)
            else:
                mixed_warnings.append(entry)

        self.contract_report["mixed_sentence_warnings"] = mixed_warnings[:5]
        if attempt == 1:
            self.contract_report["quote_precheck_errors"] = [
                self._quote_check_payload(check, "quote_contract") for check in quote_errors[:5]
            ] + mixed_errors[:5]
            if quote_errors or mixed_errors:
                self.contract_report["repair_triggered"] = True
                self.contract_report["repair_count"] = 1
        elif quote_errors or mixed_errors:
            self.contract_report["final_errors"] = [
                self._quote_check_payload(check, "quote_contract") for check in quote_errors[:5]
            ] + mixed_errors[:5]
            self.contract_report["passed_after_repair"] = False
        else:
            self.contract_report["passed_after_repair"] = True

        if not quote_errors and not mixed_errors:
            if attempt == 1:
                self.contract_report["passed_after_repair"] = True
            return

        message = format_quote_contract_error(quote_errors)
        if mixed_errors:
            mixed_lines = [
                f"- claim_id={entry['claim_id']} code=mixed_sentence_factual_absence "
                f"claim={entry['claim']!r}"
                for entry in mixed_errors[:5]
            ]
            message += (
                "\nmixed_sentence_violation: factual_claim must not contain an "
                "absence clause. Split it into one factual claim and one "
                "non_factual/absence claim (support_status=null, evidence_refs=[]).\n"
                + "\n".join(mixed_lines)
            )
        if len(message) > 2000:
            message = message[:1999] + "…"
        raise QuoteContractError(message)

    @staticmethod
    def _quote_check_payload(check: QuoteCheck, code: str) -> dict[str, Any]:
        return {
            "claim_id": check.claim_id,
            "context_id": check.context_id,
            "code": check.error or code,
            "quote": (check.quote or "")[:300],
            "context_excerpt": (check.context_excerpt or "")[:300] or None,
        }

    def _repair_example(self) -> str | None:
        """给修复轮一条完整合法 JSON，避免长 schema 导致半截输出。"""
        if self.metric == "faithfulness":
            if self.prompt_version == CONTRACT_REPAIR_VERSION:
                # v1.2.3-only repair example: complete context quote + legal absence.
                # Must not contain Q23/生鲜食品/fixture-specific sentences.
                return json.dumps(
                    {
                        "claims": [
                            {
                                "claim_id": "cl1",
                                "claim": "商品在签收后 24 小时内出现质量问题的，需提交照片反馈",
                                "claim_type": "factual_claim",
                                "claim_subtype": "policy",
                                "support_status": "supported",
                                "is_contradictory": False,
                                "contradiction_with": [],
                                "evidence_refs": [
                                    {
                                        "context_id": "C1",
                                        "quote": ("商品在签收后 24 小时内出现质量问题的，" "需提交照片反馈。"),
                                    }
                                ],
                                "reason": "quote 从 context 完整连续复制；answer 的截断句不是证据",
                            },
                            {
                                "claim_id": "cl2",
                                "claim": "文档未说明超时后的申诉渠道",
                                "claim_type": "non_factual",
                                "claim_subtype": "absence",
                                "support_status": None,
                                "is_contradictory": False,
                                "contradiction_with": [],
                                "evidence_refs": [],
                                "reason": "absence 不需要证据",
                            },
                        ],
                        "reason": "",
                    },
                    ensure_ascii=False,
                )
            if self.prompt_version == "v1.2.2":
                # v1.2.2-only repair example: legal non_factual absence.
                # Do not change v1.2.0/v1.2.1 examples below.
                return json.dumps(
                    {
                        "claims": [
                            {
                                "claim_id": "cl1",
                                "claim": "订单签收后 7 天内可申请无理由退款",
                                "claim_type": "factual_claim",
                                "claim_subtype": "policy",
                                "support_status": "supported",
                                "is_contradictory": False,
                                "contradiction_with": [],
                                "evidence_refs": [
                                    {
                                        "context_id": "C1",
                                        "quote": "订单签收后 7 天内可申请无理由退款。",
                                    }
                                ],
                                "reason": "C1 原文",
                            },
                            {
                                "claim_id": "cl2",
                                "claim": "文档未提及超时后的申诉渠道",
                                "claim_type": "non_factual",
                                "claim_subtype": "absence",
                                "support_status": None,
                                "is_contradictory": False,
                                "contradiction_with": [],
                                "evidence_refs": [],
                                "reason": "absence 不需要证据",
                            },
                        ],
                        "reason": "",
                    },
                    ensure_ascii=False,
                )
            if self.schema_version in (JUDGE_SCHEMA_V2, JUDGE_SCHEMA_V3):
                return json.dumps(
                    {
                        "claims": [
                            {
                                "claim_id": "cl1",
                                "claim": "订单签收后 7 天内可申请无理由退款",
                                "claim_type": "factual_claim",
                                "claim_subtype": "policy",
                                "support_status": "supported",
                                "is_contradictory": False,
                                "contradiction_with": [],
                                "evidence_refs": [
                                    {
                                        "context_id": "C1",
                                        "quote": "订单签收后 7 天内可申请无理由退款。",
                                    }
                                ],
                                "reason": "C1 原文",
                            }
                        ],
                        "reason": "",
                    },
                    ensure_ascii=False,
                )
            return json.dumps(
                {
                    "claims": [
                        {
                            "claim": "订单签收后 7 天内可申请无理由退款",
                            "supported": True,
                            "evidence": ["订单签收后 7 天内可申请无理由退款。"],
                            "reason": "C1 原文",
                        }
                    ],
                    "reason": "",
                },
                ensure_ascii=False,
            )
        if self.metric == "answer_correctness":
            return json.dumps(
                {
                    "score": 0.8,
                    "missing_points": [],
                    "wrong_facts": [],
                    "reason": "关键事实正确",
                },
                ensure_ascii=False,
            )
        return json.dumps(
            {"score": 0.9, "reason": "直接回答了问题"},
            ensure_ascii=False,
        )

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


__all__ = [
    "PROMPT_DIR",
    "RagJudgeAgent",
    "RagJudgePromptError",
    "load_judge_prompt",
    "load_prompt_manifest",
    "resolve_prompt_version",
]
