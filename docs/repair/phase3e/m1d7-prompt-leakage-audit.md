# M1-D-7 v1.2.5 Prompt 泄漏审计

> 状态：`pass`；最小匹配长度：12 个归一化字符。
> 来源：docs\repair\phase3e\pilot-10-v1.1.5-gate.json, docs\repair\phase3e\m1d3-judge-only-results.json, docs\repair\phase3e\m1d4-single-case-results.json, docs\repair\phase3e\m1d6-single-case-results.json
> 审计对象：faithfulness.txt, answer_correctness.txt, answer_relevancy.txt, patch_example.json
> findings：0；未 whitelist：0

## 按 Prompt

| Prompt | findings |
|---|---:|

## 按 Case

| Case | findings |
|---|---:|

## Findings

| Prompt | 行 | Case | 来源 | 匹配文本 | 长度 | whitelist |
|---|---:|---|---|---|---:|---|
| — | — | — | — | 无 | 0 | — |

## 规则

- contexts 全文不进 Prompt 审计（运行时本来会输入 contexts）。
- answer、gold_answer、Judge claim、evidence quote 的 ≥12 字符共享子串必须为 0。
- 任何 whitelist 必须逐条写明“不是任一 gate case 的 claim/evidence”。
