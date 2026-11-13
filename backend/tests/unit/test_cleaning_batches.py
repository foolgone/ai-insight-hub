"""清洗分批：把长文本切成多个 LLM 调用，避免推理模型输出被 max_tokens 截断。

背景（2026-11-13 线上）：50 行 CSV 一次调用耗时 18s 后输出
``finish_reason=length``（7282 reasoning + 4k 正文 > 4096 上限），
JSON 被截断 → ``cleaning output contains no dialogues`` → 任务失败。
"""
from __future__ import annotations

import pytest

from app.services.cleaning_service import _split_text_batches

pytestmark = pytest.mark.unit


def test_short_text_returns_single_batch_unchanged() -> None:
    text = "q,a\n你好,您好"
    assert _split_text_batches(text, max_chars=1000) == [text]


def test_long_csv_is_split_and_keeps_header() -> None:
    header = "question,answer"
    rows = [f"问题{i},答案{i}" for i in range(50)]
    text = "\n".join([header, *rows])

    batches = _split_text_batches(text, max_chars=200)

    assert len(batches) > 1
    assert all(batch.startswith(header) for batch in batches), "每批都要带表头，模型才知道列含义"
    # 所有数据行都保留，且不重复
    restored = [line for batch in batches for line in batch.splitlines()[1:]]
    assert restored == rows


def test_batches_respect_size_limit() -> None:
    header = "question,answer"
    text = "\n".join([header, *[f"问题{i},答案{i}" for i in range(80)]])

    batches = _split_text_batches(text, max_chars=120)

    for batch in batches:
        # 只在单行本身超长时才允许突破
        assert len(batch) <= 120 + len(header) + 1


def test_overlong_single_line_is_hard_split() -> None:
    text = "q,a\n" + "x" * 250

    batches = _split_text_batches(text, max_chars=100)

    assert len(batches) >= 3
    restored = "".join(batch.splitlines()[1] for batch in batches)
    assert restored == "x" * 250, "超长单行必须硬切且不丢字符"


def test_non_csv_text_has_no_phantom_header() -> None:
    text = "\n".join(f"第{i}行内容" for i in range(30))

    batches = _split_text_batches(text, max_chars=50)

    restored = [line for batch in batches for line in batch.splitlines()]
    assert restored == [f"第{i}行内容" for i in range(30)]
