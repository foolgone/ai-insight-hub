# Prompt 金标准基线（Golden Baseline）

本目录用于存放清洗 Agent 的金标准输出，供 `pytest -m prompt` 做语义/结构对比。

## 当前状态

- 结构断言已落地：`tests/prompt/test_cleaning_prompts.py`（50 条用例，校验 JSON 结构、计数一致性、质量分 0-100）。
- 语义金标准（`golden_outputs/*.json`）**待首次真实跑批后生成**：需要人工确认样本后由负责人执行：

```powershell
# 1) 生成候选输出（会调用真实 LLM，产生 token 费用）
pytest -m prompt tests/prompt -v
# 2) 将确认后的输出按 cases/<case-id>.json 存入本目录
# 3) 后续用 REGENERATE_GOLDEN=1 重新生成基线
```

## 约定

- 每个金标准文件包含 `input`（原始文本）与 `expected`（人工确认的关键字段：
  `cleaned_records`、`dialogues[*].quality_score` 区间、`avg_quality_score` 区间）。
- 语义对比使用相似度阈值（≥0.85）而非逐字相等，避免模型正常波动导致误报。
- 未完成的语义基线在 B-315 中标注为「待首次真实跑批」，不计入 CI 门禁。
