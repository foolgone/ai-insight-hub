# M1-C C4 40 条完整性盘点（非 Judge 运行）

> 状态：`static_inventory_not_judge_run`；生成日期 2026-11-20。
> 目标：`pilot-40-targets-v1.2.0-v1.0.2.json` SHA256 `3ee15dfca66fe13f0a45fda84ecf2612483f2de107ad079b196a6bd6344d5846`
> 分类：`pilot-40-final-labels.json` SHA256 `f139623fef80b55716fce0c773e776d284a5167683eb91559b23e49cabd000eb`
> 脚本：`m1c_c4_inventory.py` SHA256 `6909fce36d71652d3fde28dda211f06f61f8ea377fe0212a08145892a7c00d24`
> 输出：`m1c-c4-inventory.json` SHA256 `581b71589b801849e7f6c045aead88d67741d164a0689ca1bae5b51eecc9d326`

## 计数

- total: 40
- group: {'provisional': 27, 'human_gold': 13}
- category: {'direct': 12, 'multi': 8, 'constraint': 9, 'unanswerable': 6, 'ambiguous': 5}
- baseline: {'reused': 30, 'new': 2, 'missing': 6, 'available_old_run': 2}
- context: {'2': 32, 'unavailable': 2, '1': 6}

## 特殊列表

- `baseline_missing`: ['Q33', 'Q34', 'Q37', 'Q38', 'Q39', 'Q40']
- `baseline_delta`: unavailable for ['Q33', 'Q34', 'Q37', 'Q38', 'Q39', 'Q40']
- `context_unavailable`: ['Q14', 'Q33']
- `c1_only`: ['Q22', 'Q26', 'Q27', 'Q34', 'Q37', 'Q40']
- `available_old_run`: ['Q35', 'Q36']
- `new_baseline`: ['Q14', 'Q32']
- `known_non_pass`: ['Q14']
- `category_changed`: ['Q40']

## 40 条明细

| Case | group | category | context | baseline | delta | target F | known issue |
|---|---|---|---|---|---|---|---|
| Q01 | provisional | direct | 2 | reused | available | [0.9, 1.0] |  |
| Q02 | provisional | direct | 2 | reused | available | None |  |
| Q03 | provisional | direct | 2 | reused | available | None |  |
| Q04 | provisional | direct | 2 | reused | available | [1.0, 1.0] |  |
| Q05 | human_gold | direct | 2 | reused | available | None |  |
| Q06 | provisional | direct | 2 | reused | available | None |  |
| Q07 | provisional | direct | 2 | reused | available | None |  |
| Q08 | provisional | direct | 2 | reused | available | None |  |
| Q09 | provisional | direct | 2 | reused | available | None |  |
| Q10 | provisional | direct | 2 | reused | available | None | evidence_typo_history |
| Q11 | provisional | multi | 2 | reused | available | [0.6, 0.9] | normative_requirement |
| Q12 | provisional | multi | 2 | reused | available | None | conditional_inference |
| Q13 | human_gold | multi | 2 | reused | available | None |  |
| Q14 | human_gold | multi | unavailable | new | unavailable | unavailable | context_unavailable;C_variance;known_non_pass |
| Q15 | human_gold | direct | 2 | reused | available | [0.6, 1.0] | purpose_inference |
| Q16 | human_gold | constraint | 2 | reused | available | None | R_overstrict_history |
| Q17 | provisional | multi | 2 | reused | available | [0.7, 0.9] | policy_relationship_target_reapproval |
| Q18 | provisional | multi | 2 | reused | available | None |  |
| Q19 | human_gold | multi | 2 | reused | available | [0.6, 1.0] | absence_meta_classification |
| Q20 | provisional | multi | 2 | reused | available | [0.6, 1.0] | policy_scope_generalization |
| Q21 | provisional | constraint | 2 | reused | available | [0.6, 0.7] | Q21#3_insufficient |
| Q22 | human_gold | constraint | 1 | reused | available | [0.8, 1.0] | cross_line_quote_history |
| Q23 | human_gold | constraint | 2 | reused | available | [0.4, 0.5] | quote_synthesis_history;internal_contradiction |
| Q24 | provisional | constraint | 2 | reused | available | None | extra_condition_inference |
| Q25 | provisional | constraint | 2 | reused | available | None | C_exact_0.10 |
| Q26 | provisional | constraint | 1 | reused | available | None | C1_only |
| Q27 | provisional | constraint | 1 | reused | available | None | C1_only |
| Q28 | provisional | constraint | 2 | reused | available | [0.8, 1.0] | compensation_inference |
| Q29 | provisional | unanswerable | 2 | reused | available | skipped | correct_skip |
| Q30 | human_gold | unanswerable | 2 | reused | available | [0.4, 1.0] | policy_scope_target_reapproval |
| Q31 | provisional | unanswerable | 2 | reused | available | [0.6, 1.0] | quote_absence_diagnostic |
| Q32 | provisional | unanswerable | 2 | new | unavailable | [0.9, 1.0] | uncertainty_misclass |
| Q33 | provisional | unanswerable | unavailable | missing | unavailable | None | context_unavailable;not_run |
| Q34 | provisional | unanswerable | 1 | missing | unavailable | None | C1_only;not_run |
| Q35 | human_gold | ambiguous | 2 | available_old_run | old_run_only | [0.8, 1.0] | absence_quote_diagnostic |
| Q36 | human_gold | ambiguous | 2 | available_old_run | old_run_only | [0.8, 1.0] | condition_sentence;conflict_disclosure |
| Q37 | human_gold | ambiguous | 1 | missing | unavailable | None | C1_only;not_run |
| Q38 | provisional | ambiguous | 2 | missing | unavailable | None |  |
| Q39 | provisional | ambiguous | 2 | missing | unavailable | None |  |
| Q40 | human_gold | direct | 1 | missing | unavailable | None | C1_only;not_run;category_changed |

## 边界

- 本文件是静态盘点，不是 Judge 运行；
- `baseline_missing` 不计算 delta，不声称改善/回退；
- Q14/Q33 context_unavailable 不进入 F 目标通过率；
- C1-only 单列；Q35/Q36 只用 old run 参考；
- 未修改 Prompt/Service/Schema/API/DB；未运行 Judge。
