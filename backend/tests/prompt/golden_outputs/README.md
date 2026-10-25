# Prompt 金标准基线（Golden Baseline）

本目录用于存放 5 个 Agent 的金标准输出，供 `pytest -m prompt` 做结构/语义对比。

## 当前覆盖（B-607）

| Agent | 用例数 | 文件 |
|---|---|---|
| 清洗 | 50 | `tests/prompt/test_cleaning_prompts.py` |
| 质量评估 | 50 | `tests/prompt/test_evaluation_prompts.py` |
| 知识提取 | 50 | `tests/prompt/test_extraction_prompts.py` |
| 洞察分析 | 50 | `tests/prompt/test_insight_prompts.py` |
| 报告生成 | 50 | `tests/prompt/test_report_prompts.py` |

结构断言已全部落地（JSON 结构/计数/量纲/质量分 0-100/情感和=1 等）。

## Golden 基线流程

```powershell
# 1) 生成/更新基线（真实 LLM 调用，产生 token 费用；人工确认后提交）
$env:REGENERATE_GOLDEN = "1"
pytest -m prompt tests/prompt -v
Remove-Item Env:REGENERATE_GOLDEN

# 2) 普通回归（只读基线；无基线时跳过语义对比，结构断言始终执行）
pytest -m prompt tests/prompt -v
```

工具入口：`tests/prompt/golden.py`（`load_golden` / `save_if_requested` / `assert_or_record`）。

## 约定

- 基线文件 `<name>.json` 包含 `input` 与人工确认的关键指标（计数、分数区间、情感和）。
- 语义对比用相似度阈值（≥0.85），不做逐字相等，避免模型正常波动误报。
- 5 Agent 各 50 条用例默认排除（`pytest.ini` 的 `-m "not prompt"`），不计入 CI 门禁。
