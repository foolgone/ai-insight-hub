"""凭据加解密服务（BYOK，需求 §6 / §15）。

安全约束：
- ``CREDENTIAL_ENCRYPTION_KEY`` 缺失/格式非法 → 抛 ``LLMCredentialDecryptError``
  （fail closed，**不退化为明文存储**）；
- ``decrypt`` 失败（密钥不匹配/密文损坏）→ 同一异常类，对外 500；
- ``key_hint`` 固定格式：前 5 位 + ``…`` + 后 4 位（调用前已保证 len >= 12）；
- 任何路径都不返回、不打印明文 Key。
"""
from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings
from app.core.exceptions import LLMCredentialDecryptError

__all__ = ["decrypt", "encrypt", "ensure_encryption_ready", "make_hint"]


def _get_fernet() -> Fernet:
    key = settings.CREDENTIAL_ENCRYPTION_KEY
    if not key:
        raise LLMCredentialDecryptError("CREDENTIAL_ENCRYPTION_KEY 未配置，无法保存或读取凭据")
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError) as exc:
        raise LLMCredentialDecryptError("CREDENTIAL_ENCRYPTION_KEY 格式非法（需 32 字节 base64）") from exc


def encrypt(plaintext: str) -> str:
    """加密明文 Key，返回 Fernet 密文（base64 字符串）。"""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """解密密文；失败抛 ``LLMCredentialDecryptError``。"""
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise LLMCredentialDecryptError("凭据解密失败，加密密钥可能已更换") from exc


def make_hint(api_key: str) -> str:
    """展示用掩码：前 5 位 + ``…`` + 后 4 位（如 ``sk-x…a1b2``）。"""
    return f"{api_key[:5]}…{api_key[-4:]}"


def ensure_encryption_ready() -> None:
    """保存前快速失败：密钥缺失/非法时先抛 500，避免白花一次 verify 的调用。"""
    _get_fernet()
