"""T8 PDF 报告渲染单测（reportlab，中文 CID 字体，不依赖数据库）。"""
from __future__ import annotations

import uuid

import pytest

from app.models import Report
from app.services.report_service import render_pdf

pytestmark = pytest.mark.unit

OUTPUT = {
    "title": "测试报告",
    "report_type": "quality",
    "generated_at": "2026-10-26T10:00:00",
    "summary": "整体质量良好。",
    "sections": [
        {"title": "概览", "content": "共评估 10 条。\n\n- 平均分 86.2\n- 需复核 1 条"},
        {"title": "## 详细分析", "content": "**准确性** 最高；`合规性` 需关注。"},
    ],
    "highlights": ["平均 86.2"],
    "recommendations": ["补充标准答案"],
    "metadata": {"insight_degraded": False},
}


def _report(**overrides) -> Report:
    return Report(
        id=uuid.uuid4(),
        datasource_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        title=overrides.pop("title", "测试报告"),
        report_type=overrides.pop("report_type", "quality"),
        format="pdf",
        config=overrides.pop("config", {}),
        **overrides,
    )


def test_render_pdf_returns_pdf_bytes() -> None:
    content = render_pdf(_report(), OUTPUT, {})

    assert content.startswith(b"%PDF")
    assert content.rstrip().endswith(b"%%EOF")
    assert len(content) > 1000


def test_render_pdf_handles_empty_sections() -> None:
    content = render_pdf(_report(title="空报告"), {"summary": "", "sections": []}, {})

    assert content.startswith(b"%PDF")
    assert len(content) > 500


def test_render_pdf_accepts_time_range_config() -> None:
    report = _report(config={"time_range": {"start": "2026-10-01", "end": "2026-10-26"}})

    content = render_pdf(report, OUTPUT, {})

    assert content.startswith(b"%PDF")
