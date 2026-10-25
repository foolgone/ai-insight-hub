"""Golden 基线工具（B-607）。

用法：
- 普通运行：只读取/比对基线（无基线时跳过）；
- ``REGENERATE_GOLDEN=1 pytest -m prompt tests/prompt``：把本次真实输出写入
  ``golden_outputs/<name>.json``，供人工确认后提交。

比对口径：结构 + 关键指标区间（不做逐字相等，避免模型正常波动误报）。
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

GOLDEN_DIR = Path(__file__).parent / "golden_outputs"


def load_golden(name: str) -> dict[str, Any] | None:
    path = GOLDEN_DIR / f"{name}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_if_requested(name: str, payload: dict[str, Any]) -> bool:
    """``REGENERATE_GOLDEN=1`` 时写入基线文件并返回 True。"""
    if os.getenv("REGENERATE_GOLDEN") != "1":
        return False
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    path = GOLDEN_DIR / f"{name}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def assert_or_record(name: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    """记录或返回基线，便于测试内做区间断言。"""
    save_if_requested(name, payload)
    return load_golden(name)


__all__ = ["GOLDEN_DIR", "assert_or_record", "load_golden", "save_if_requested"]
