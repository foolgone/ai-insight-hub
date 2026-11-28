# M1-D-6 5-case 模型对比申请（qwen-max + qwen3.8-flash，F only）

> 状态：`pending_approval`；**未跑 Judge、未写 PASS、未改 target。**
> 日期：2026-11-24；revision r1
> application：`docs/repair/phase3e/m1d6-v125-model-comparison-5case-application.json`（SHA `3c172380…`）
> preflight：`docs/repair/phase3e/m1d6-v125-model-comparison-5case-preflight.json`（SHA `1b85d717…`）
> 资产：v1.2.5 frozen；F `9c80d4d5…`；freeze `e9e5f8e`；agent `318b302`。
> target：active **v1.0.2**；v1.0.3 draft **不参与评分**。

## 1. 目的

回答一个问题：**3 个 invalid case（Q23/Q35/Q36）的失败，是 qwen-max 的能力瓶颈，还是 harness/规则问题？**

同条件双 arm、同 5 cases、同 Prompt、同 target：

| arm | model | 设置 |
|---|---|---|
| A1 | `qwen-max` | DashScope；历史 baseline 模型，本次同 case 重跑 |
| A2 | `qwen3.8-flash` | DashScope；`enable_thinking=false` |

不启动 flash 全量重新基线；不在本次切换模型。

## 2. 凭据与端点确认

| 检查 | 结果 |
|---|---|
| `GET /models` | 200；191 个模型 |
| qwen-max chat | **200**（充值后恢复；最小 JSON 探针） |
| qwen3.8-flash chat（thinking off） | **200** |
| flash thinking on（1.5k prompt） | 200，但 reasoning 3649；7k prompt 会撞满 8192 |
| flash thinking off（6.8k prompt） | 200，631 输出，`finish_reason=stop` |

## 3. 范围与预算

| 项 | 值 |
|---|---|
| cases | Q23 / Q35 / Q36 / Q17 / Q21 |
| runs | 每 case × 每 arm 1 次 |
| 指标 | F only（含 `faithfulness_strict`） |
| primary | **10** |
| patch reserve | 10 |
| retry reserve | 3 |
| max calls | **23** |
| 估算（上界） | **CNY 0.42** |
| ceiling | **CNY 0.60** |

估算依据：qwen-max 历史 18 calls = CNY 0.1971；flash 6 calls = CNY 0.1577；两 arm 合计留出余量。

## 4. 重点观察

1. Q23/Q35：`factual_claim + absence` 是否在 flash 下消失；
2. Q36：`patch evidence_refs:null` 是否复现；
3. Q17/Q21：在 **cl3 修正口径**下的 F（只观察，不改 target）；
4. 两 arm 的 claim 粒度、patch 行为、invalid 数；
5. 是否值得换模型。

## 5. 决策表

| 观察 | 下一步 |
|---|---|
| flash invalid 明显更少、Q23/Q35/Q36 转 valid | 提模型切换提案 + 重新基线 |
| 两 arm invalid 数接近 | invalid 不是模型单方面问题；进 contract harness / 规则评估 |
| flash 在 Q17/Q21 的 F 低于 qwen-max | 模型切换有代价；先选定模型，再校准 target |
| 两 arm 仍复现 patch_null / factual+absence | contract/harness 为主；停止 prompt-only |

## 6. 边界

- diagnostic only；5 cases × 2 arms × F only × 1 次；
- target 用 active v1.0.2；v1.0.3 draft 不参与；
- 不写 PASS、不计入 10 条、不跑正式 10/40；
- 不激活 v1.2.5；默认仍 `v1.0.0`；
- 不改 frozen 资产/Prompt/Agent/Service/validator/fixture；
- 不启动 flash 全量重新基线；不出 v1.2.6；
- M1-D-6 仍 `blocked`；M1-C/M1-D 未 accepted。
