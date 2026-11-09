"""转写文本结构化 Schemas（内容路由：QA / 知识点 / 摘要）。"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ContentType = Literal["interview", "customer_service", "meeting", "monologue", "other"]
StructureKind = Literal["qa", "knowledge", "summary"]


class StructureInput(BaseModel):
    """结构化入参：一段（通常来自 ASR 的）纯文本。"""

    text: str
    duration: float | None = None
    channel_mode: str | None = None


class QAItem(BaseModel):
    """一组问答。角色由模型判断：question 是提问方，answer 是回答方。"""

    question: str = ""
    answer: str = ""
    quality_score: float | None = Field(default=None, ge=0, le=100)
    issues: list[str] = Field(default_factory=list)


class KnowledgeItem(BaseModel):
    title: str = ""
    content: str = ""
    tags: list[str] = Field(default_factory=list)


class StructureOutput(BaseModel):
    """结构化结果：模型先判断内容类型，再决定用哪种形态承载。"""

    content_type: ContentType = "other"
    structure: StructureKind = "summary"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    qa: list[QAItem] = Field(default_factory=list)
    knowledge: list[KnowledgeItem] = Field(default_factory=list)
    summary: str | None = None
    # 模型自述的判断依据，便于排查（不展示给用户）
    rationale: str | None = None


__all__ = [
    "ContentType",
    "KnowledgeItem",
    "QAItem",
    "StructureInput",
    "StructureKind",
    "StructureOutput",
]
