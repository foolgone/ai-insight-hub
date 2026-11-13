"""任务进度可见性（#6）与失败文件可重新清洗（#7）。

背景（2026-11-13 E2E）：
- 50 条评估要跑 8 分钟，DB 只在结束时提交，前端全程显示 pending/0%；
- 「新建清洗任务」只挑 `status=pending` 的 raw，失败文件永远选不到，
  任务建出来后 5% 失败 `no raw data to clean`。
"""
from __future__ import annotations

import pytest

from app.services.evaluation_service import (
    PROGRESS_COMMIT_EVERY,
    should_commit_progress,
)

pytestmark = pytest.mark.unit


def test_progress_commits_only_on_interval() -> None:
    assert should_commit_progress(commit=True, index=PROGRESS_COMMIT_EVERY) is True
    assert should_commit_progress(commit=True, index=PROGRESS_COMMIT_EVERY * 2) is True
    assert should_commit_progress(commit=True, index=1) is False


def test_progress_never_commits_without_commit_flag() -> None:
    # 单测用调用方的会话，绝不能替它提交事务
    assert all(
        should_commit_progress(commit=False, index=index) is False
        for index in (0, 1, PROGRESS_COMMIT_EVERY, PROGRESS_COMMIT_EVERY * 3)
    )
