# 10 条 Pilot 重跑：v1.0.0 vs v1.1.1（新 F SHA）

> 同一批 Pilot answer/contexts；v1.1.1 使用新 F Prompt SHA；只切换 Judge Prompt 版本。
> Faithfulness 只用 `query.contexts`（C1–C2），不使用 retrieval contexts。

## 执行状态

- 状态：**stopped**
- 停止原因：
  - `Q01/C: dropped 0.900->0.700 >0.10 without target`
- 已完成案例：**1/10**
- 未运行案例：Q04, Q11, Q17, Q21, Q23, Q29, Q31, Q35, Q36
- 模型：`qwen-max`；temperature=0.0；max_tokens=8192
- v1.1.1 新 F SHA：`4ee65afb3e7ea8b4b5e361e41ea75b74173142a8c26c97dedc7139ba37c86317`
- v1.0.0 复用案例：Q01

## Arm 配置

| Arm | schema | rubric | metric | F SHA | C SHA | R SHA |
|---|---|---|---|---|---|---|
| v1.0.0 | rag_judge_schema_v1 | v1.0.0 | v1 | `287053e9e67ad29fd2de597d1052b8d418040097910462e4a0f176b14295bfed` | `106e11f2bc39806da5ecf090c6dbcd94d81ca5f53b968e5055d5a33833b30f94` | `27203126964ae0ca8f0bb8641cb3c2b145605cec706ef47c5432a0bbd6fad141` |
| v1.1.1 | rag_judge_schema_v2 | v1.1.1 | v2 | `4ee65afb3e7ea8b4b5e361e41ea75b74173142a8c26c97dedc7139ba37c86317` | `35631c071418fcaf3d6b49a75a92ce2d6d70c7d3da9f381e164e4785f769f7c8` | `0f8576b7dbf2e7ea1a02752680b0afe8c66677fe2eda823f4bcd28371ae4da84` |

## 逐案例

### Q01 · direct

- 问题：退款申请期限是多久？
- Gold：ai_draft_pending_human（docs/repair/phase3e/candidates.json (AI draft, pending human)）
- v1.0.0 复用：True

| 指标 | v1.0.0 | v1.1.1 | Δ |
|---|---|---|---|
| F | 1.000 | 1.000 | +0.000 |
| C | 0.900 | 0.700 | -0.200 |
| R | 0.800 | 0.900 | +0.100 |

- Correctness details：`{"missing_points": [], "wrong_facts": [], "reason": "回答基本正确，但包含了一些不必要的额外信息。"}`

- Counts（v1.1.1）：scorable=5, supported=5, unsupported=0, insufficient=0, non_factual=0, document_conflict=0, contradiction=0
- evidence：5/5 ok；validation_errors=[]

| claim_id | claim（截断） | type/subtype | status | evidence |
|---|---|---|---|---|
| cl1 | 退款申请期限为订单签收后7天内 | factual_claim/policy | supported | 1 |
| cl2 | 定制类商品、生鲜食品、已激活的虚拟商品不支持无理由退款 | factual_claim/policy | supported | 1 |
| cl3 | 生鲜食品如存在质量问题，须在签收后24小时内拍照反馈 | factual_claim/policy | supported | 1 |
| cl4 | 虚拟商品（如充值、会员、课程）一经售出不支持退款 | factual_claim/policy | supported | 1 |
| cl5 | 定制商品仅支持因质量问题退换，不支持无理由退换 | factual_claim/policy | supported | 1 |

## 发现

- **停止条件命中：Q01 v1.1.1 Correctness 0.900→0.700（-0.200）**，Q01 不在 6 案例矩阵、无目标解释，按“未解释单指标下降 >0.10”立即停止。
- Q01 v1.1.1 C 的 `missing_points=[]`、`wrong_facts=[]`，reason 为“回答基本正确，但包含了一些不必要的额外信息”——不是事实错误，但 rubric 对“额外信息”的扣分明显重于 v1.0.0。
- Q01 F 1.0→1.0；R 0.8→0.9（+0.1）。
- Q01 v1.0.0 为指纹一致复用；v1.1.1 使用新 F SHA。
- 未运行 Q04/Q11/Q17/Q21/Q23/Q29/Q31/Q35/Q36；**Q36 disclosure 未验证**。

## Token / 成本（仅 Q01 × 2 臂）

| Arm | input | output | 估算成本（CNY） |
|---|---|---|---|
| v1.0.0 | 3605 | 499 | 0.0134 |
| v1.1.1 | 7648 | 735 | 0.0254 |
| **合计** |  |  | **0.0388** |

> v1.0.0 为复用结果，其 token 是上一轮已发生成本；本表按本轮汇总口径并列展示。

## 边界

- v1.1.1 仍 `design_draft` / `active=false`；脚本退出前恢复 `RAG_JUDGE_PROMPT_VERSION=v1.0.0`。
- 未跑 40 条、未激活、未改 Human Gold/Prompt 正文/DB。
- 共享 `parse_with_repair` 的 Schema fallback 已修复并补测；该修复不改变 RagJudge 的完整示例路径。

