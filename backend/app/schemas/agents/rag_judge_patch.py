"""v1.2.4 evidence-only patch schema.

Patch output can only replace a claim's evidence_refs. It deliberately does not
expose claim text, type, subtype, support_status, contradiction fields or reason.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.agents.rag_judge import EvidenceRef


class EvidenceFix(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str = Field(min_length=1, max_length=64)
    evidence_refs: list[EvidenceRef] = Field(min_length=1, max_length=20)


class EvidencePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fixes: list[EvidenceFix] = Field(min_length=1, max_length=20)


__all__ = ["EvidenceFix", "EvidencePatch"]
