# M1-D-6 Q17 / Q21 Target 复核（M1-A desk，r2：按裁决修正 Q21 cl3）

> 状态：`read_only_review`；**未跑 Judge、未改 target v1.0.2、未改 Prompt/Agent/fixture。**
> 日期：2026-11-24；revision **r2**
> 证据：`docs/repair/phase3e/m1d6-q17-q21-target-review.json`（SHA `800de34f…`）
> 数据源：flash 对比结果 `efdfa729…`；qwen-max failure-mode `309fa9b8…`；target v1.0.2 `3ee15dfc…`；fixture `dc7be14b…`
> 资产：v1.2.5 frozen；F `9c80d4d5…`；freeze `e9e5f8e`；agent `318b302`。

## 0. 结论（r2）

| case | 旧 target | flash F | qwen-max F | 旧 target 是否成立 | v1.0.3 draft 建议 |
|---|---|---:|---:|---|---|
| Q17 | `[0.7, 0.9]` | **0.5**（4 claims） | 0.6（5 claims） | **否**：下界不可达 | **`[0.5, 0.7]`** |
| Q21 | `[0.6, 0.7]` | **0.5**（2/4，cl3 修正后） | 0.6（3/5，cl3 修正后） | **否**：旧区间方向错误 | **`[0.5, 0.7]`** |

两者都是 **valid**，问题是 target 校准，不是 Judge 稳定性。

r2 相对 r1 的修正：

1. Q17 建议区间从 `[0.4, 0.7]` 改为 `[0.5, 0.7]`：`0.4` 会让“少一条 supported”的欠支持结果也通过。
2. **Q21 cl3 从 `supported_with_caveat` 改为 `insufficient_evidence`**，并按此重算 F。
3. Q21 建议区间从 `[0.7, 0.9]` 改为 `[0.5, 0.7]`：旧建议会把过支持放行。

## 1. Q17

### 1.1 数据

| 项 | flash | qwen-max |
|---|---:|---:|
| F | **0.5** | 0.6 |
| claims | 4 | 5 |
| supported | 2 | 3 |
| insufficient | 2 | 2 |
| unsupported | 0 | 0 |

### 1.2 逐 claim 语义判定

| claim | 类型 | flash | qwen-max | 判定 |
|---|---|---|---|---|
| 满 99 元包邮适用于正向发货环节 | policy_scope | insufficient | insufficient | **insufficient 合理**：上下文只写“满 99 元包邮；未满收 10 元”，没有显式“正向发货”范围 |
| 退货时的运费承担方取决于退换货原因 | condition | 未拆出 | supported | **supported**：上下文并列了两条责任归属 |
| 质量问题退换货运费商家承担 | policy | supported | supported | supported（§7 原文） |
| 非质量问题退货运费买家承担 | policy | supported | supported | supported（§7 原文） |
| 退货运费责任与是否满 99 无关 | policy_relationship | insufficient | insufficient | **insufficient 合理**：上下文没有显式关系句 |

### 1.3 为什么 `[0.7, 0.9]` 不成立

- 两条 insufficient（scope、relationship）在 v1.2.0 语义规范下正确；
- 诚实分数上限是 3/5 = **0.6**（qwen-max）或 2/4 = **0.5**（flash）；
- `0.7` 下界要求至少 3.5/5 supported，不可达。

### 1.4 为什么用 `[0.5, 0.7]` 而不是 `[0.4, 0.7]`

| 区间 | 覆盖 0.5/0.6 | 拒绝 0.4 欠支持 | 判断 |
|---|---|---|---|
| `[0.4, 0.7]` | ✅ | ❌：0.4 也会通过 | 过松 |
| **`[0.5, 0.7]`** | ✅ | ✅ | 采用 |

### 1.5 附带发现：claim 分解不稳定

flash 少拆“取决于退换货原因”这条 supported claim，分母 5→4、F 0.6→0.5。target 需要为分解差异留余量，这也是 `[0.5,0.7]` 下界取 0.5 的原因。

## 2. Q21

### 2.1 数据（cl3 修正后）

| 项 | flash | qwen-max |
|---|---:|---:|
| F（原） | 0.75 | 0.8 |
| **F（cl3=insufficient）** | **0.5** | **0.6** |
| claims | 5 | 6 |
| scorable | 4 | 5 |
| supported | 2 | 3 |
| insufficient | 2 | 2 |
| non_factual | 1 | 1 |

### 2.2 逐 claim 语义判定

| claim | 类型 | flash | qwen-max | 判定 |
|---|---|---|---|---|
| 第 10 天不支持无理由退款 | derived | supported | supported | supported（7 天窗口推导） |
| 无理由退款仅限 7 天内 | policy | supported | supported | supported（§1 原文） |
| 限制适用于普通商品（非定制/生鲜/虚拟） | condition | ~~supported~~ → **insufficient** | ~~supported~~ → **insufficient** | **insufficient**：cl3 是排除项的补集推断；§5.2 要求 condition 不得只凭主题词或反推 |
| 质量问题不受 7 天无理由限制 | condition | insufficient | insufficient | insufficient：上下文无该豁免条款 |
| 建议联系客服 | advice | non_factual | non_factual | 不计入分母 |

### 2.3 cl3 裁决

| 项 | 值 |
|---|---|
| 原判定 | `supported_with_caveat` |
| 裁决后 | **`insufficient_evidence`** |
| 依据 | v1.2.2 既有决策 + v1.2.5 Prompt §5.2：condition / policy_scope / policy_relationship 只凭主题词或反推不够 |
| 决策人 | 项目决策角色（代江晚） |
| 日期 | 2026-11-24 |

### 2.4 为什么 `[0.7, 0.9]` 不能接受

- cl3 修正后，诚实分数是 0.5 / 0.6；
- `[0.7, 0.9]` 的下界 0.7 高于诚实分数上限 0.6，等于要求模型把补集推断判 supported；
- 这会把“过支持”行为放行，方向与 M1 的可信度目标相反。

### 2.5 为什么用 `[0.5, 0.7]`

- 覆盖 flash 0.5、qwen-max 0.6；
- 上界 0.7 能拒绝 0.75/0.8 的过支持结果；
- 如果未来 M1-A 重新裁决 cl3 为 supported，再单独讨论，不在本次静默放宽。

## 3. 决策表

| 项 | 当前 | v1.0.3 draft |
|---|---|---|
| Q17 F | `[0.7, 0.9]` | **`[0.5, 0.7]`** |
| Q21 F | `[0.6, 0.7]` | **`[0.5, 0.7]`** |
| target 版本 | v1.0.2（active） | v1.0.3-draft（不激活） |
| 生效条件 | — | M1-A 审核 + 新 SHA + 重新基线 |

## 4. 边界

- 只做 desk review；0 Judge calls；
- target v1.0.2 未修改；v1.0.3 仅为 draft，未激活；
- 未改 Prompt/Agent/Service/validator/fixture；
- 未写 PASS、未激活、未跑正式 10/40；
- M1-D-6 仍 `blocked`；M1-C/M1-D 未 accepted。
