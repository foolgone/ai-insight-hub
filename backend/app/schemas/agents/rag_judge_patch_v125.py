"""v1.2.5 evidence-only patch schema with explicit refusal.

Patch output can either replace evidence refs for all flagged claims or refuse
the whole patch. Refusal is a first-class failure, never a silent downgrade.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.agents.rag_judge import EvidenceRef


class EvidenceFixV125(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str = Field(min_length=1, max_length=64)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list, max_length=20)


class EvidenceRefusalV125(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_ids: list[str] = Field(min_length=1, max_length=20)
    reason_code: Literal[
        "no_direct_quote",
        "quote_not_contiguous",
        "claim_requires_split",
        "other",
    ]
    reason: str = Field(min_length=1, max_length=500)


class EvidencePatchV125(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fixes: list[EvidenceFixV125] = Field(default_factory=list, max_length=20)
    refusal: EvidenceRefusalV125 | None = None

    @model_validator(mode="after")
    def _validate_shape(self) -> EvidencePatchV125:
        if self.refusal is not None and self.fixes:
            raise ValueError("fixes and refusal are mutually exclusive")
        if self.refusal is None and not self.fixes:
            raise ValueError("fixes or refusal is required")
        return self


__all__ = ["EvidenceFixV125", "EvidenceRefusalV125", "EvidencePatchV125"]
