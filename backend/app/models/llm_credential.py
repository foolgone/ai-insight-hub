"""UserLLMCredential ORM 模型（BYOK，数据库设计新表 ``user_llm_credentials``）。

一个用户最多一条有效凭据（``user_id`` 唯一）；密文落库，接口只回显 ``key_hint``。
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class UserLLMCredential(Base):
    """用户 LLM 凭据表（Fernet 密文存储）。"""

    __tablename__ = "user_llm_credentials"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'invalid')", name="status_valid"),
        Index("uk_user_llm_credentials_user_id", "user_id", unique=True),
        Index("idx_user_llm_credentials_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default=text("'deepseek'")
    )
    # Phase 1：保存时非空即拒绝（SSRF 防护）；Phase 2 开放时须加 URL 白名单
    base_url: Mapped[str | None] = mapped_column(String(500))
    model: Mapped[str | None] = mapped_column(String(100))
    encrypted_api_key: Mapped[str] = mapped_column(Text, nullable=False)
    # 固定格式：前 5 位 + … + 后 4 位（如 sk-x…a1b2），不可还原明文
    key_hint: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'active'"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
