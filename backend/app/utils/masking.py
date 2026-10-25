"""日志脱敏工具（B-702；可观测文档 §3.3）。

只做兜底：日志不应记录完整 Prompt/模型输出；确需记录时先调用本工具。
顺序：身份证 → 手机号 → 邮箱，避免长数字被手机号规则截断。
"""
from __future__ import annotations

import re

_ID_RE = re.compile(r"\b(\d{6})(\d{8})(\d{4})\b")
_PHONE_RE = re.compile(r"\b(1[3-9]\d)(\d{4})(\d{4})\b")
_EMAIL_RE = re.compile(r"([A-Za-z0-9._%+-])([A-Za-z0-9._%+-]*)(@[A-Za-z0-9.-]+)")


def mask_pii(text: str) -> str:
    """脱敏身份证号、手机号、邮箱。"""
    if not text:
        return text
    masked = _ID_RE.sub(r"\1********\3", text)
    masked = _PHONE_RE.sub(r"\1****\3", masked)
    masked = _EMAIL_RE.sub(r"\1***\3", masked)
    return masked


__all__ = ["mask_pii"]
