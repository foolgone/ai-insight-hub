# M1-D-6 Target v1.0.3 Draft（不激活）

> 状态：**draft**；v1.0.2 仍为 active；本文件不激活、不覆盖旧文件。
> 日期：2026-11-24
> draft：`docs/repair/phase3e/pilot-40-targets-v1.2.0-v1.0.3-draft.json`
> draft SHA：`50aeda481d188484d6021ea4632535076ed8626dbcbdd0dcb8bb1b3d52ce47dc`
> validation：`docs/repair/phase3e/pilot-40-targets-v1.2.0-v1.0.3-draft-validation.json`
> validation SHA：`d500f4cb8d7046d9e6f65b44c5dfd032ec92599fa6b1c91af84ea659285da3bd`（21/21 pass）
> base：`pilot-40-targets-v1.2.0-v1.0.2.json`（SHA `3ee15dfc…`，**未修改**）
> 上游：`61-m1d6-q17-q21-target-review.md`（r2；Q21 cl3 = insufficient）
> rubric：v1.2.0；Prompt：v1.2.5 frozen；freeze `e9e5f8e`；agent `318b302`。

## 1. 变更范围

只改两条，其余 38 条逐字段不变：

| case | 字段 | v1.0.2 | v1.0.3 draft | 依据 |
|---|---|---|---:|---|
| Q17 | `targets.F` | `[0.7, 0.9]` | **`[0.5, 0.7]`** | flash 0.5 / qwen-max 0.6；scope、relationship 均正确 insufficient；0.4 会放行欠支持 |
| Q21 | `targets.F` | `[0.6, 0.7]` | **`[0.5, 0.7]`** | cl3 按 §5.2 判 insufficient；flash 0.5 / qwen-max 0.6；上界 0.7 拒绝 0.75/0.8 过支持 |

Q17 的 C/R target 保持 `[0.8,1.0]`；Q21 仍只有 F target。

## 2. Draft 元信息

| 项 | 值 |
|---|---|
| `meta.version` | `v1.0.3-draft` |
| `meta.status` | `draft_pending_m1a_review` |
| `meta.active` | `false` |
| `meta.based_on` | `pilot-40-targets-v1.2.0-v1.0.2.json` |
| `meta.based_on_sha256` | `3ee15dfc…` |
| `meta.change_scope` | `Q17.F and Q21.F only` |
| `meta.draft_at` | 2026-11-24 |
| frozen 字段 | 已移除（draft 不冻结） |

## 3. Validation（21/21 pass）

| 检查 | 结果 |
|---|---|
| draft JSON 可解析 | ✅ |
| version / status / active | ✅ `v1.0.3-draft` / `draft_pending_m1a_review` / `false` |
| draft 未冻结 | ✅ 无 `frozen_at` / `frozen_by` |
| 40 cases、case_id 顺序一致 | ✅ |
| 只有 Q17.Q21 变更 | ✅ |
| Q17.F / Q21.F = `[0.5,0.7]` | ✅ |
| 其余 target 字段不变 | ✅ |
| 所有区间合法（含 `[1.0,1.0]`、`unavailable`、`skipped` 哨兵） | ✅ |
| 其余 38 条 target_status 不变 | ✅ |
| review 中 Q21 cl3 = insufficient | ✅ |
| review 推荐区间 = `[0.5,0.7]` | ✅ |
| v1.0.2 SHA 未变 | ✅ `3ee15dfc…` |

## 4. 生效路径

1. M1-A 审核 draft；
2. 审核通过后生成 **正式 v1.0.3**（新 SHA），v1.0.2 退出 active；
3. 在选定模型上重新基线；
4. 再谈 10 条 diagnostic / 正式 10/40。

**当前不激活、不改默认、不覆盖 v1.0.2。**

## 5. 边界

- draft only；0 Judge calls；
- target v1.0.2 未修改、仍 active；
- 未改 Prompt/Agent/Service/validator/fixture；
- 未写 PASS、未跑正式 10/40；
- M1-D-6 仍 `blocked`。
