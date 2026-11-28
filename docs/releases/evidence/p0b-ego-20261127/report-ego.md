# P0B 类人测试 Run 对比报告 20261127

- 报告类型：综合分析报告
- 生成时间：2026-11-27T14:01:27.784600
- 时间范围：未指定

## 摘要

本报告对比 Run ea63f595（Base）与 ab7a19d2（Target）：5 个 Case 中变好 0、变差 1、不变 4、invalid 0、未处理 0。Judge 为 beta，delta 不代表因果变化，不能作为优化效果。

## 质量评估概览

本报告为 Run 对比报告，不含质量评估数据

## 知识库概览

本报告为 Run 对比报告，不含知识库数据

## 洞察概览

本报告为 Run 对比报告，不含洞察数据

## 核心发现

- F 0.000
- C -0.020
- R +0.020
- Case 变好 0 / 变差 1 / 不变 4

## Run 对比

### Base / Target

| 项 | Base | Target |
| --- | --- | --- |
| Run ID | `ea63f595-e6ab-46fa-a362-32cce6b0bf32` | `ab7a19d2-cf56-4f3c-a7d0-d833e97b9b98` |
| 数据集 | P0B 类人测试评测集 20261127 | P0B 类人测试评测集 20261127 |
| 版本 | `0e7234e6` | `0e7234e6` |
| 模式 / Adapter / top_k | query / mock / 3 | query / mock / 5 |
| 模型 / Prompt | qwen-flash / v1.0.0 | qwen-flash / v1.0.0 |
| 完成时间 | 2026-11-27T13:58:55.631159 | 2026-11-27T13:59:35.859696 |

### 指标对比

| 指标 | Base | Target | Δ |
| --- | --- | --- | --- |
| Faithfulness | 0.600 | 0.600 | 0.000 |
| Answer Correctness | 0.320 | 0.300 | -0.020 |
| Answer Relevancy | 0.480 | 0.500 | +0.020 |

### 样本状态

| 样本状态 | Base | Target |
| --- | --- | --- |
| 已评分 | 5 | 5 |
| invalid | 0 | 0 |
| 失败 | 0 | 0 |
| 跳过 | 0 | 0 |
| 未处理 | 0 | 0 |

### Case 汇总

- 变好 0 / 变差 1 / 不变 4 / invalid 0 / 未处理 0（合计 5）
- 对齐后 Case：5；本次导出/对比：5

### Top 变好（最多 5）

（无）

### Top 变差（最多 5）

| Case | 问题 | 驱动指标 | Δ | 说明 |
| --- | --- | --- | --- | --- |
| Q001 | 退款多久到账？ | answer_correctness | -0.100 | C -0.100 |

### 说明与噪声提示

> **Judge beta 噪声提示**：Judge 为 beta；同配置/同输入的两条 Run 也可能出现 ±0.2 波动。delta 不代表因果变化，不能直接当作优化效果；建议重复 3 次或确认 RAG 输入/配置确实不同后再判断。
> 导出：在 [对比页](/rag-evaluations/compare?base=ea63f595-e6ab-46fa-a362-32cce6b0bf32&target=ab7a19d2-cf56-4f3c-a7d0-d833e97b9b98) 使用「导出 CSV / 导出 JSON」；导出文件含 noise_notice 与 same_config。

## 改进建议

- 无
