"""阶段一一致性修复的单元测试（不依赖数据库）。

覆盖：
- ``load_prompt_version``：取首个 vX.Y.Z 行 / 文件缺失回退（P1-7）
- ``_parse_timestamp``：非法/缺失返回 None（P1-6）
- ``_client_ip``：X-Forwarded-For / X-Real-IP / socket 回退（P1-2）
- ``_load_raw_text``：截断且无对象名时回退入库文本（P1-1）
- ``task_service._dispatch_retry``：按 task_type 分派 / 未知类型报错（P0-3）
"""
from __future__ import annotations

from pathlib import Path

import pytest
from starlette.requests import Request

from app.composition import enqueue, executors
from app.agents.base import load_prompt_version
from app.core.exceptions import TaskNotRetryableError
from app.models import RawData, Task
from app.services import task_service
from app.services.cleaning_service import _load_raw_text, _parse_timestamp
from app.middleware.rate_limit import _client_ip


# --------------------------------------------------------------------- P1-7


def test_load_prompt_version_reads_first_line(tmp_path: Path) -> None:
    (tmp_path / "version.txt").write_text(
        "v1.1.0\n2026-10-27\n- 新增规则 8\n\nv1.0.0\n- 初始版本\n", encoding="utf-8"
    )
    assert load_prompt_version(tmp_path) == "v1.1.0"


def test_load_prompt_version_fallback_when_missing(tmp_path: Path) -> None:
    assert load_prompt_version(tmp_path, default="v9.9.9") == "v9.9.9"


def test_real_prompt_dirs_have_versions() -> None:
    """5 个 Agent 的 prompts 目录都必须能解析出版本号。"""
    prompts = Path(__file__).resolve().parents[2] / "app" / "prompts"
    for name in ("cleaning", "evaluation", "extraction", "insight", "reports"):
        version = load_prompt_version(prompts / name, default="")
        assert version.startswith("v"), f"{name} 缺少 version.txt"


# --------------------------------------------------------------------- P1-6


@pytest.mark.parametrize("value", [None, "", "not-a-date", 12345, {}])
def test_parse_timestamp_invalid_returns_none(value) -> None:
    assert _parse_timestamp(value) is None


def test_parse_timestamp_iso_with_timezone() -> None:
    parsed = _parse_timestamp("2026-11-06T10:00:00+08:00")
    assert parsed is not None
    assert parsed.tzinfo is None
    assert parsed.hour == 2  # 转成 UTC naive


# --------------------------------------------------------------------- P1-2


def _request(headers: dict[str, str], client=("127.0.0.1", 1234)) -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    return Request({"type": "http", "headers": raw, "client": client})


def test_client_ip_prefers_forwarded_for_first_hop() -> None:
    request = _request({"X-Forwarded-For": "203.0.113.9, 10.0.0.1"})
    assert _client_ip(request) == "203.0.113.9"


def test_client_ip_falls_back_to_real_ip_then_socket() -> None:
    assert _client_ip(_request({"X-Real-IP": "198.51.100.7"})) == "198.51.100.7"
    assert _client_ip(_request({})) == "127.0.0.1"


# --------------------------------------------------------------------- P1-1


def test_load_raw_text_falls_back_when_object_missing() -> None:
    raw = RawData(
        datasource_id=None,
        raw_content={"text": "stored-text", "truncated": True},
        file_info={"filename": "a.csv"},
    )
    assert _load_raw_text(raw) == "stored-text"


def test_load_raw_text_uses_records_when_no_text() -> None:
    raw = RawData(
        datasource_id=None,
        raw_content={"records": [{"a": 1}], "truncated": False},
        file_info={},
    )
    assert _load_raw_text(raw) == '[{"a": 1}]'


# --------------------------------------------------------------------- P0-3


@pytest.mark.asyncio
async def test_dispatch_retry_clean(monkeypatch) -> None:
    monkeypatch.setattr(enqueue, "enqueue_clean", lambda task_id: "celery-clean-1")
    task = Task(task_type="clean", params={})
    assert await task_service._dispatch_retry(None, task, executors.dispatch) == "celery-clean-1"


@pytest.mark.asyncio
async def test_dispatch_retry_unknown_type_raises() -> None:
    task = Task(task_type="unknown", params={})
    with pytest.raises(TaskNotRetryableError):
        await task_service._dispatch_retry(None, task, executors.dispatch)
