"""凭据加解密单测（AC-BK-04 / 09 的单元层）。"""
from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from app.core import credential_encryption as crypto
from app.core.config import settings
from app.core.exceptions import LLMCredentialDecryptError

pytestmark = pytest.mark.unit

KEY = "sk-userkey0000000000"


@pytest.fixture(autouse=True)
def fernet_key(monkeypatch):
    monkeypatch.setattr(settings, "CREDENTIAL_ENCRYPTION_KEY", Fernet.generate_key().decode())


def test_encrypt_decrypt_roundtrip() -> None:
    ciphertext = crypto.encrypt(KEY)
    assert ciphertext != KEY
    assert "sk-" not in ciphertext
    assert crypto.decrypt(ciphertext) == KEY


def test_make_hint_is_first5_last4() -> None:
    hint = crypto.make_hint(KEY)
    assert hint == "sk-us…0000"
    assert "…" in hint
    assert len(hint) == 10


def test_missing_key_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr(settings, "CREDENTIAL_ENCRYPTION_KEY", "")
    with pytest.raises(LLMCredentialDecryptError):
        crypto.encrypt(KEY)
    with pytest.raises(LLMCredentialDecryptError):
        crypto.ensure_encryption_ready()


def test_invalid_key_format_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr(settings, "CREDENTIAL_ENCRYPTION_KEY", "not-a-fernet-key")
    with pytest.raises(LLMCredentialDecryptError):
        crypto.encrypt(KEY)


def test_decrypt_with_rotated_key_raises(monkeypatch) -> None:
    ciphertext = crypto.encrypt(KEY)
    monkeypatch.setattr(settings, "CREDENTIAL_ENCRYPTION_KEY", Fernet.generate_key().decode())
    with pytest.raises(LLMCredentialDecryptError):
        crypto.decrypt(ciphertext)
