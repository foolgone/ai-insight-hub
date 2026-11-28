"""Run 对比报告章节（P1-3b，确定性渲染，不调用 LLM）。

数据来自对比页已对齐的结果快照（``ReportConfig.run_comparison``），
由 ``report_service`` 追加到现有报告模板的 sections 中；报告仍走原有
markdown / excel / pdf 渲染与存储链路。
"""
from __future__ import annotations

from typing import Any

from app.schemas.agents.report import RunComparisonCase, RunComparisonPayload

NOISE_NOTICE = (
    "Judge 为 beta；同配置/同输入的两条 Run 也可能出现 ±0.2 波动。"
    "delta 不代表因果变化，不能直接当作优化效果；建议重复 3 次或确认 "
    "RAG 输入/配置确实不同后再判断。"
)
SAME_CONFIG_NOTICE = (
    "两条 Run 的数据集/版本、adapter、mode、top_k 相同（或配置不可得）；" "当前 delta 主要反映 Judge beta 噪声，不能作为优化结论。"
)


def _fmt_score(value: float | None) -> str:
    return "—" if value is None else f"{value:.3f}"


def _fmt_delta(value: float | None) -> str:
    if value is None:
        return "—"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.3f}"


def _short(value: str | None, length: int = 8) -> str:
    return value[:length] if value else "—"


def _one_line(value: str | None) -> str:
    if not value:
        return "—"
    return " ".join(str(value).split())


def _table(headers: list[str], rows: list[list[str]]) -> str:
    head = "| " + " | ".join(headers) + " |"
    divider = "| " + " | ".join("---" for _ in headers) + " |"
    body = ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join([head, divider, *body])


def _side_table(payload: RunComparisonPayload) -> str:
    base = payload.base
    target = payload.target
    rows = [
        ["Run ID", f"`{base.run_id}`", f"`{target.run_id}`"],
        ["数据集", _one_line(base.dataset_name), _one_line(target.dataset_name)],
        [
            "版本",
            f"`{_short(base.dataset_version_id)}`",
            f"`{_short(target.dataset_version_id)}`",
        ],
        [
            "模式 / Adapter / top_k",
            f"{base.execution_mode or '—'} / {base.adapter or '—'} / "
            f"{base.top_k if base.top_k is not None else '—'}",
            f"{target.execution_mode or '—'} / {target.adapter or '—'} / "
            f"{target.top_k if target.top_k is not None else '—'}",
        ],
        [
            "模型 / Prompt",
            f"{base.judge_model or '—'} / {base.prompt_version or '—'}",
            f"{target.judge_model or '—'} / {target.prompt_version or '—'}",
        ],
        ["完成时间", base.completed_at or "—", target.completed_at or "—"],
    ]
    return _table(["项", "Base", "Target"], rows)


def _metric_table(payload: RunComparisonPayload) -> str:
    rows = [
        [
            row.label or row.metric_name,
            _fmt_score(row.base),
            _fmt_score(row.target),
            _fmt_delta(row.delta),
        ]
        for row in payload.metrics
    ]
    if not rows:
        rows = [["—", "—", "—", "—"]]
    return _table(["指标", "Base", "Target", "Δ"], rows)


def _sample_table(payload: RunComparisonPayload) -> str:
    base = payload.base
    target = payload.target
    rows = [
        [
            "已评分",
            str(base.evaluated_items if base.evaluated_items is not None else "—"),
            str(target.evaluated_items if target.evaluated_items is not None else "—"),
        ],
        [
            "invalid",
            str(base.invalid_items if base.invalid_items is not None else "—"),
            str(target.invalid_items if target.invalid_items is not None else "—"),
        ],
        [
            "失败",
            str(base.failed_items if base.failed_items is not None else "—"),
            str(target.failed_items if target.failed_items is not None else "—"),
        ],
        [
            "跳过",
            str(base.skipped_items if base.skipped_items is not None else "—"),
            str(target.skipped_items if target.skipped_items is not None else "—"),
        ],
        [
            "未处理",
            str(base.unprocessed_items if base.unprocessed_items is not None else "—"),
            str(target.unprocessed_items if target.unprocessed_items is not None else "—"),
        ],
    ]
    return _table(["样本状态", "Base", "Target"], rows)


def _case_table(items: list[RunComparisonCase]) -> str:
    if not items:
        return "（无）"
    rows = []
    for item in items:
        label = item.item_key or _short(item.dataset_item_id)
        rows.append(
            [
                label,
                _one_line(item.question),
                item.driver_metric or "—",
                _fmt_delta(item.driver_delta),
                _one_line(item.note),
            ]
        )
    return _table(["Case", "问题", "驱动指标", "Δ", "说明"], rows)


def render_comparison_content(payload: RunComparisonPayload) -> str:
    """生成「Run 对比」章节 Markdown 内容。"""
    summary = payload.case_summary
    total = summary.total or (
        summary.improved
        + summary.regressed
        + summary.unchanged
        + summary.invalid
        + summary.unprocessed
    )
    lines = [
        "### Base / Target",
        "",
        _side_table(payload),
        "",
        "### 指标对比",
        "",
        _metric_table(payload),
        "",
        "### 样本状态",
        "",
        _sample_table(payload),
        "",
        "### Case 汇总",
        "",
        f"- 变好 {summary.improved} / 变差 {summary.regressed} / 不变 {summary.unchanged} / "
        f"invalid {summary.invalid} / 未处理 {summary.unprocessed}（合计 {total}）",
        f"- 对齐后 Case：{summary.aligned_total or total}；本次导出/对比：{summary.exported_cases or total}",
    ]
    if summary.case_truncated:
        lines.append("- 截断说明：" + (summary.truncation_note or "仅对比前 200 个 Case，报告数字仅覆盖已对比部分。"))
    lines.extend(
        [
            "",
            "### Top 变好（最多 5）",
            "",
            _case_table(payload.top_improved),
            "",
            "### Top 变差（最多 5）",
            "",
            _case_table(payload.top_regressed),
            "",
            "### 说明与噪声提示",
            "",
            f"> **Judge beta 噪声提示**：{NOISE_NOTICE}",
        ]
    )
    if payload.same_config:
        lines.append(f"> **同配置比较**：{SAME_CONFIG_NOTICE}")
    if payload.compare_url:
        lines.append(
            f"> 导出：在 [对比页]({payload.compare_url}) 使用「导出 CSV / 导出 JSON」；"
            "导出文件含 noise_notice 与 same_config。"
        )
    else:
        lines.append("> 导出：在对比页使用「导出 CSV / 导出 JSON」。")
    return "\n".join(lines)


def build_comparison_output(
    report: Any, payload: RunComparisonPayload, *, generated_at: str | None = None
) -> dict[str, Any]:
    """构建与 ReportOutput 兼容的确定性输出（不调用报告 Agent）。"""
    summary = payload.case_summary
    total = summary.total or (
        summary.improved
        + summary.regressed
        + summary.unchanged
        + summary.invalid
        + summary.unprocessed
    )
    base_label = _short(payload.base.run_id)
    target_label = _short(payload.target.run_id)
    summary_text = (
        f"本报告对比 Run {base_label}（Base）与 {target_label}（Target）："
        f"{total} 个 Case 中变好 {summary.improved}、变差 {summary.regressed}、"
        f"不变 {summary.unchanged}、invalid {summary.invalid}、未处理 {summary.unprocessed}。"
        "Judge 为 beta，delta 不代表因果变化，不能作为优化效果。"
    )
    if summary.case_truncated:
        summary_text += summary.truncation_note or "仅对比前 200 个 Case，报告数字仅覆盖已对比部分。"

    highlights: list[str] = []
    for row in payload.metrics:
        if row.delta is not None:
            highlights.append(f"{row.metric_short or row.metric_name} {_fmt_delta(row.delta)}")
    highlights.append(
        f"Case 变好 {summary.improved} / 变差 {summary.regressed} / 不变 {summary.unchanged}"
    )
    if payload.same_config:
        highlights.append("同配置比较：delta 主要反映 Judge beta 噪声")

    return {
        "title": getattr(report, "title", "Run 对比报告"),
        "report_type": getattr(report, "report_type", "comprehensive"),
        "generated_at": generated_at,
        "summary": summary_text,
        "sections": [
            {
                "title": "Run 对比",
                "content": render_comparison_content(payload),
            }
        ],
        "highlights": highlights,
        "recommendations": [],
        "metadata": {
            "comparison": True,
            "source": "rag_compare",
            "same_config": payload.same_config,
            "judge_beta": True,
        },
    }


__all__ = [
    "NOISE_NOTICE",
    "SAME_CONFIG_NOTICE",
    "build_comparison_output",
    "render_comparison_content",
]
