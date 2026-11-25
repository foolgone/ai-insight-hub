"""P1-3b：Run 对比报告章节（确定性渲染）单元测试。"""
from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace

from openpyxl import load_workbook

from app.schemas.agents.report import (
    RunComparisonCase,
    RunComparisonMetric,
    RunComparisonPayload,
    RunComparisonSide,
    RunComparisonSummary,
)
from app.services import report_service
from app.services.report_comparison import (
    NOISE_NOTICE,
    SAME_CONFIG_NOTICE,
    build_comparison_output,
    render_comparison_content,
)


def _payload(*, same_config: bool = True, truncated: bool = False) -> RunComparisonPayload:
    return RunComparisonPayload(
        base=RunComparisonSide(
            run_id="5328123c-f3f5-4f6b-9d59-763c5e415719",
            dataset_name="M3 P1-2 分页验收数据集",
            dataset_version_id="43eccb08-4fca-43d1-87ca-974f523481be",
            execution_mode="query",
            adapter="mock",
            top_k=3,
            completed_at="2026-11-25T03:33:00Z",
            judge_model="qwen-flash",
            prompt_version="v1.2.5",
            total_items=120,
            evaluated_items=120,
            invalid_items=0,
            failed_items=0,
            skipped_items=0,
            unprocessed_items=0,
        ),
        target=RunComparisonSide(
            run_id="7b2fa311-760b-4064-a45e-648647102250",
            dataset_name="M3 P1-2 分页验收数据集",
            dataset_version_id="43eccb08-4fca-43d1-87ca-974f523481be",
            execution_mode="query",
            adapter="mock",
            top_k=3,
            completed_at="2026-11-25T03:44:00Z",
            judge_model="qwen-flash",
            prompt_version="v1.2.5",
            total_items=120,
            evaluated_items=120,
            invalid_items=0,
            failed_items=0,
            skipped_items=0,
            unprocessed_items=0,
        ),
        metrics=[
            RunComparisonMetric(
                metric_name="faithfulness",
                metric_short="F",
                label="Faithfulness",
                base=0.776,
                target=0.801,
                delta=0.026,
            ),
            RunComparisonMetric(
                metric_name="answer_correctness",
                metric_short="C",
                label="Answer Correctness",
                base=0.128,
                target=0.125,
                delta=-0.003,
            ),
            RunComparisonMetric(
                metric_name="answer_relevancy",
                metric_short="R",
                label="Answer Relevancy",
                base=0.498,
                target=0.488,
                delta=-0.01,
            ),
        ],
        case_summary=RunComparisonSummary(
            improved=31,
            regressed=32,
            unchanged=57,
            invalid=0,
            unprocessed=0,
            total=120,
            aligned_total=120,
            exported_cases=120 if not truncated else 200,
            case_truncated=truncated,
            truncation_note="仅导出前 200 个 Case（对齐后共 250 个）。" if truncated else None,
        ),
        top_improved=[
            RunComparisonCase(
                dataset_item_id="item-1",
                item_key="P12-001",
                question="退款申请提交后多久审批？",
                verdict="improved",
                driver_metric="answer_relevancy",
                driver_delta=0.2,
                note="R +0.200",
            )
        ],
        top_regressed=[
            RunComparisonCase(
                dataset_item_id="item-2",
                item_key="P12-002",
                question="发票什么时候开具？",
                verdict="regressed",
                driver_metric="faithfulness",
                driver_delta=-0.4,
                note="F -0.400",
            )
        ],
        same_config=same_config,
        compare_url=(
            "/rag-evaluations/compare?base=5328123c-f3f5-4f6b-9d59-763c5e415719"
            "&target=7b2fa311-760b-4064-a45e-648647102250"
        ),
    )


def test_render_comparison_content_numbers_and_notice() -> None:
    content = render_comparison_content(_payload())

    assert "`5328123c-f3f5" in content
    assert "Faithfulness" in content
    assert "+0.026" in content
    assert "-0.003" in content
    assert "变好 31 / 变差 32 / 不变 57" in content
    assert "P12-001" in content
    assert "P12-002" in content
    assert "R +0.200" in content
    assert NOISE_NOTICE in content
    assert SAME_CONFIG_NOTICE in content
    assert "导出 CSV / 导出 JSON" in content


def test_same_config_false_keeps_beta_notice_only() -> None:
    content = render_comparison_content(_payload(same_config=False))

    assert NOISE_NOTICE in content
    assert SAME_CONFIG_NOTICE not in content
    assert "**同配置比较**" not in content


def test_truncated_and_empty_top_lists() -> None:
    payload = _payload(truncated=True)
    payload.top_improved = []
    payload.top_regressed = []
    content = render_comparison_content(payload)

    assert "仅导出前 200 个 Case" in content
    assert content.count("（无）") >= 2


def test_build_comparison_output_shape() -> None:
    report = SimpleNamespace(title="Run 对比报告", report_type="comprehensive")
    output = build_comparison_output(report, _payload(), generated_at="2026-11-25T04:00:00")

    assert output["title"] == "Run 对比报告"
    assert output["generated_at"] == "2026-11-25T04:00:00"
    assert output["sections"][0]["title"] == "Run 对比"
    assert output["sections"][0]["content"]
    assert "变好 31" in output["summary"]
    assert output["recommendations"] == []
    assert output["metadata"]["comparison"] is True
    assert output["metadata"]["same_config"] is True


def test_render_markdown_uses_existing_comprehensive_template() -> None:
    report = SimpleNamespace(
        title="Run 对比报告",
        report_type="comprehensive",
        config={},
    )
    output = build_comparison_output(report, _payload(), generated_at="2026-11-25T04:00:00")

    markdown = report_service.render_markdown(report, output, {})

    assert "# Run 对比报告" in markdown
    assert "## Run 对比" in markdown
    assert "变好 31 / 变差 32 / 不变 57" in markdown
    assert "Judge beta 噪声提示" in markdown
    assert "不含质量评估数据" in markdown
    assert "不含洞察数据" in markdown


def test_render_excel_contains_comparison_section() -> None:
    report = SimpleNamespace(title="Run 对比报告", report_type="comprehensive", config={})
    output = build_comparison_output(report, _payload(), generated_at="2026-11-25T04:00:00")

    workbook = load_workbook(BytesIO(report_service.render_excel(report, output)))
    sections = workbook["Sections"]
    values = [row[0].value for row in sections.iter_rows()]
    assert "Run 对比" in values
