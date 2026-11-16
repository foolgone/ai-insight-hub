# 10 条 Pilot：v1.0.0 vs v1.1.1 真实 Judge 对比

> 固定同一批 Pilot answer/contexts，只切换 Judge Prompt 版本；未重新生成答案。
> Faithfulness 只使用 `query.contexts`（C1–C2）；未使用 retrieval contexts。
> **这是第一次真实模型对比；dry-run 不是质量证据。**

## 执行状态

- 状态：**stopped**
- 停止原因：
  - `Q17/faithfulness: schema/status failed`
- 已完成案例：**4/10**
- 未运行案例：Q21, Q23, Q29, Q31, Q35, Q36
- 模型：`qwen-max`；temperature=0.0；max_tokens=8192
- 每个案例两个 arm 使用同一 answer/contexts/gold_answer；只改 `RAG_JUDGE_PROMPT_VERSION`。

## Arm 配置

| Arm | model | temp | max_tokens | schema | rubric | metric | F SHA | C SHA | R SHA |
|---|---|---|---|---|---|---|---|---|---|
| v1.0.0 | qwen-max | 0.0 | 8192 | rag_judge_schema_v1 | v1.0.0 | v1 | `287053e9e67ad29fd2de597d1052b8d418040097910462e4a0f176b14295bfed` | `106e11f2bc39806da5ecf090c6dbcd94d81ca5f53b968e5055d5a33833b30f94` | `27203126964ae0ca8f0bb8641cb3c2b145605cec706ef47c5432a0bbd6fad141` |
| v1.1.1 | qwen-max | 0.0 | 8192 | rag_judge_schema_v2 | v1.1.1 | v2 | `913dc28f6e28973462cee8052a0f8ee7aeb95704b6c9ae151ab5937ad46d59d0` | `35631c071418fcaf3d6b49a75a92ce2d6d70c7d3da9f381e164e4785f769f7c8` | `0f8576b7dbf2e7ea1a02752680b0afe8c66677fe2eda823f4bcd28371ae4da84` |

## 分指标汇总（仅已完成案例）

| Arm | F 均值 | C 均值 | R 均值 | F 有效 | C 有效 | R 有效 | 失败 |
|---|---|---|---|---|---|---|---|
| v1.0.0 | 0.938 | 0.875 | 0.950 | 4/4 | 4/4 | 4/4 | 0 |
| v1.1.1 | 0.944 | 0.900 | 0.925 | 3/4 | 4/4 | 4/4 | 1 |

> 均值只覆盖已完成的 4 条，不能代表 10 条；Q11 F 目标未命中，见“发现”。

## 逐案例

### Q01 · direct

- 问题：退款申请期限是多久？
- Gold：ai_draft_pending_human（docs/repair/phase3e/candidates.json (AI draft, pending human)）
- 矩阵目标：无（该案例不在 6 案例验收矩阵）

| 指标 | v1.0.0 | v1.1.1 | Δ |
|---|---|---|---|
| F | 1.000 | 1.000 | +0.000 |
| C | 0.900 | 0.900 | +0.000 |
| R | 0.800 | 0.900 | +0.100 |

- Counts（v1.1.1）：scorable=5, supported=5, unsupported=0, insufficient=0, non_factual=0, document_conflict=0, contradiction=0
- evidence：5/5 ok；validation_errors=[]

| claim_id | claim（截断） | type/subtype | status | contradictory | evidence |
|---|---|---|---|---|---|
| cl1 | 退款申请期限为订单签收后7天内，可申请无理由退款 | factual_claim/policy | supported | False | 1 |
| cl2 | 定制类商品、生鲜食品、已激活的虚拟商品不支持无理由退款 | factual_claim/policy | supported | False | 1 |
| cl3 | 生鲜食品如存在质量问题，须在签收后24小时内拍照反馈 | factual_claim/policy | supported | False | 1 |
| cl4 | 虚拟商品（如充值、会员、课程）一经售出不支持退款 | factual_claim/policy | supported | False | 1 |
| cl5 | 定制商品仅支持因质量问题退换，不支持无理由退换 | factual_claim/policy | supported | False | 1 |

### Q04 · direct

- 问题：目前支持哪种发票？
- Gold：ai_draft_pending_human（docs/repair/phase3e/candidates.json (AI draft, pending human)）
- 矩阵目标：无（该案例不在 6 案例验收矩阵）

| 指标 | v1.0.0 | v1.1.1 | Δ |
|---|---|---|---|
| F | 1.000 | 1.000 | +0.000 |
| C | 0.800 | 0.900 | +0.100 |
| R | 1.000 | 1.000 | +0.000 |

- Counts（v1.1.1）：scorable=5, supported=5, unsupported=0, insufficient=0, non_factual=0, document_conflict=0, contradiction=0
- evidence：5/5 ok；validation_errors=[]

| claim_id | claim（截断） | type/subtype | status | contradictory | evidence |
|---|---|---|---|---|---|
| cl1 | 目前仅支持电子发票。 | factual_claim/policy | supported | False | 1 |
| cl2 | 电子发票在提交申请后 24 小时内发送至下单时填写的邮箱。 | factual_claim/policy | supported | False | 1 |
| cl3 | 发票抬头可在开具前修改。 | factual_claim/policy | supported | False | 1 |
| cl4 | 已开具的电子发票如需更正，须先申请红冲，再重新开具。 | factual_claim/policy | supported | False | 1 |
| cl5 | 不支持纸质发票和增值税专用发票。 | factual_claim/policy | supported | False | 1 |

### Q11 · multi

- 问题：签收第 5 天的定制商品可以无理由退款吗？
- Gold：ai_draft_pending_human（docs/repair/phase3e/candidates.json (AI draft, pending human)）
- **Provisional：该案例不是 Human Gold。**
- 矩阵目标：`{"F": [0.6, 0.8], "C": [0.8, 1.0], "R": [0.9, 1.0]}`

| 指标 | v1.0.0 | v1.1.1 | Δ |
|---|---|---|---|
| F | 0.750 | 0.833 | +0.083 |
| C | 0.900 | 0.900 | +0.000 |
| R | 1.000 | 0.900 | -0.100 |

- Counts（v1.1.1）：scorable=6, supported=5, unsupported=0, insufficient=1, non_factual=0, document_conflict=0, contradiction=0
- evidence：5/5 ok；validation_errors=[]

| claim_id | claim（截断） | type/subtype | status | contradictory | evidence |
|---|---|---|---|---|---|
| cl1 | 不可以。 | factual_claim/policy | supported | False | 1 |
| cl2 | 订单签收后 7 天内可申请无理由退款。 | factual_claim/policy | supported | False | 1 |
| cl3 | 定制类商品不支持无理由退款。 | factual_claim/policy | supported | False | 1 |
| cl4 | 若该定制商品存在质量问题，则仍可依据第12条“特殊商品”条款申请退换货。 | factual_claim/policy | supported | False | 1 |
| cl5 | 用户当前仅可就质量问题发起售后申请。 | factual_claim/policy | supported | False | 1 |
| cl6 | 需提供相应凭证（如照片、视频等），由商家审核认定后处理。 | factual_claim/policy | insufficient_evidence | False | 0 |

### Q17 · multi

- 问题：订单满 99 元包邮，退货时运费谁承担？
- Gold：ai_draft_pending_human（docs/repair/phase3e/candidates.json (AI draft, pending human)）
- 矩阵目标：无（该案例不在 6 案例验收矩阵）

| 指标 | v1.0.0 | v1.1.1 | Δ |
|---|---|---|---|
| F | 1.000 | failed | n/a |
| C | 0.900 | 0.900 | +0.000 |
| R | 1.000 | 0.900 | -0.100 |

**Faithfulness failed：**

- error：`StructuredOutputError: structured output is still invalid after repair`
- token_usage：`{"input": 2874, "output": 687}`
- judge_config：`{"agent": "rag_judge_faithfulness", "model": "qwen-max", "temperature": 0.0, "max_tokens": 8192, "prompt_version": "v1.1.1", "resolved_prompt_version": "v1.1.1", "prompt_sha256": "913dc28f6e28973462cee8052a0f8ee7aeb95704b6c9ae151ab5937ad46d59d0", "schema_version": "rag_judge_schema_v2", "rubric_version": "v1.1.1", "metric_version": "v2"}`
- raw_output：295 chars（截断/非法 JSON）

```json
{
  "claims": [
    {
      "claim_id": "cl1",
      "claim": "订单满 99 元包邮适用于正向发货环节",
      "claim_type": "factual_claim",
      "claim_subtype": "policy",
      "support_status": "supported",
      "is_contradictory": false,
      "contradiction_with": null,
      "evidence_refs":":[{" }]
    }
```

## 发现

- **停止条件命中：Q17 v1.1.1 Faithfulness schema failed**；首次输出非法，修复轮后仍非法，`raw_output` 仅 295 chars 且 JSON 在 `evidence_refs` 处截断。按批准边界停止，未继续 Q21/Q23/Q29/Q31/Q35/Q36。
- **Q11 F 目标未命中**：v1.1.1 F=0.833（5/6 supported + 1 insufficient），高于矩阵 0.6–0.8 上限；v1.0.0=0.75。该差异不是分数下降，但属于验收目标未命中，需在进入 40 条前处理。
- Q11 R=0.9（v1.0.0 1.0，Δ-0.1），处于矩阵 0.9–1.0 下界；未超过 0.10 下降阈值。
- Q01 R +0.1、Q04 C +0.1、Q17 R -0.1；均未超过 0.10，未触发停止。
- 已完成案例的 v1.1.1 未出现 duplicate claim_id 或 duplicate/nested conflict evidence；`validation_errors` 均为空（Q17 在 schema 阶段失败，未进入 Service）。
- **Q36 未运行**，因此本轮没有 Q36 disclosure 判定；不能据此判断冲突披露是否修复。

## Token / 成本（仅已完成 4 条 × 2 臂）

| Arm | input tokens | output tokens | 估算成本（CNY） |
|---|---|---|---|
| v1.0.0 | 11278 | 1838 | 0.0447 |
| v1.1.1 | 24418 | 3093 | 0.0883 |
| **合计** |  |  | **0.1330** |

> 成本按 Pilot 的 qwen-max 公开价估算（输入 ¥0.0024/1K、输出 ¥0.0096/1K）；项目 `cost` 字段仍为 0，以 DashScope 账单为准。

## P2 处理

- Q17 是 schema failed，报告按 **failed** 标记，未当作合理的 `skipped(no_scorable_claims)`。
- 本轮已完成案例没有 skipped 行；后续若出现 skipped，报告从 Arm 级 `prompt_sha256` 取 SHA。
- `MANIFEST.active` 仅元数据；显式 `RAG_JUDGE_PROMPT_VERSION` 才是开关；脚本退出前已恢复 v1.0.0。
- 未跑 40 条、未激活、未改 Human Gold/Prompt 正文/DB。

