"""用户可配置外部地址的安全校验单测（SSRF 防护）。"""
from __future__ import annotations

import pytest

from app.core.config import settings
from app.core.url_guard import UnsafeUrlError, assert_safe_base_url

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def url_guard_env(monkeypatch):
    monkeypatch.setattr(settings, "ASR_ALLOW_HTTP", False)
    monkeypatch.setattr(settings, "ASR_ALLOWED_HOSTS", "asr.example.com")


def test_allowlisted_host_passes_and_is_normalized() -> None:
    assert assert_safe_base_url("https://asr.example.com/v1/") == "https://asr.example.com/v1"


def test_https_required_by_default() -> None:
    with pytest.raises(UnsafeUrlError):
        assert_safe_base_url("http://asr.example.com/v1")


def test_http_allowed_when_switch_on(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ASR_ALLOW_HTTP", True)
    assert assert_safe_base_url("http://asr.example.com/v1") == "http://asr.example.com/v1"


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1/v1",
        "https://10.0.0.8/v1",
        "https://192.168.1.10:8443/v1",
        "https://169.254.169.254/latest",
        "https://[::1]/v1",
        "https://localhost/v1",
    ],
)
def test_private_targets_rejected(url: str) -> None:
    with pytest.raises(UnsafeUrlError):
        assert_safe_base_url(url)


def test_credentials_in_url_rejected() -> None:
    with pytest.raises(UnsafeUrlError):
        assert_safe_base_url("https://user:pass@asr.example.com/v1")


def test_query_string_rejected() -> None:
    with pytest.raises(UnsafeUrlError):
        assert_safe_base_url("https://asr.example.com/v1?token=1")


def test_empty_rejected() -> None:
    with pytest.raises(UnsafeUrlError):
        assert_safe_base_url("   ")


def test_unresolvable_host_rejected() -> None:
    with pytest.raises(UnsafeUrlError):
        assert_safe_base_url("https://does-not-exist.invalid/v1")
