# POC 验证脚本（P1 / M2）

> 对应任务：B-101（LLM 协议）、B-102（pgvector）、B-103（自研编排）、B-104（成本）。
> **本目录不进主 CI**：`pytest.ini` 的 `norecursedirs` 已排除 `tests/poc`，需显式运行。

## 运行方式

```powershell
cd backend
.\venv\Scripts\Activate.ps1

# 全部 POC（-s 显示实测数据）
pytest tests/poc -v -s

# 单独运行
pytest tests/poc/test_llm_client.py -v -s     # 需有效 DEEPSEEK_API_KEY
pytest tests/poc/test_pgvector.py -v -s       # 需 pgvector + sentence-transformers
pytest tests/poc/test_orchestrator.py -v -s   # 无外部依赖
pytest tests/poc/test_cost_tracking.py -v -s  # 无外部依赖
```

## 前置条件与跳过规则

| POC | 依赖 | 未满足时 |
|---|---|---|
| B-101 | `DEEPSEEK_API_KEY`（非占位值） | `pytest.skip`，报告记为「待验证」 |
| B-102 | PostgreSQL + pgvector（`DATABASE_URL`）、sentence-transformers（质量用例） | 连不上则失败（需先启动 VM）；模型不可用则质量用例 skip，性能用例仍执行 |
| B-103 | 无 | — |
| B-104 | 无（单价来自配置） | — |

## 注意

- POC 会创建并删除临时表 `poc_embeddings_*`，不会污染业务表。
- 真实调用会产生 token 费用（单次 POC 约几十~几百 token）；单价未配置时成本记为 0（D-09）。
- POC 脚本只用于验证可行性，**不进入生产代码**；生产实现见 `app/core/llm.py`（B-200）与 `app/agents/workflow.py`（B-604）。
