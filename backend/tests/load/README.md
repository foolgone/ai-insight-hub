# 性能测试（B-701）

## 目标

| 指标 | 目标 |
|---|---|
| 100 并发下读接口 P95 | < 2s |
| 1 万知识条目检索 P95 | < 500ms（pg_trgm + HNSW） |
| 10 万向量检索 P95 | < 1s（HNSW，需先灌数据） |
| 成本 | 压测只打读接口，不触发 LLM；成本不变 |

## 运行

```powershell
cd backend
pip install locust
# 准备一个已绑定数据源的测试账号（不要用真实业务账号）
$env:LOAD_TEST_EMAIL = "loadtest@example.com"
$env:LOAD_TEST_PASSWORD = "secret123"
locust -f tests/load/locustfile.py --host http://127.0.0.1:8000 --headless -u 100 -r 10 -t 3m
```

结果在 Locust 控制台查看 `P95`、`Requests/s`、`Failures`；写报告时记录：
- 机器规格、DB/Redis 部署方式；
- 并发数、持续时间、P50/P95/P99；
- 慢接口与瓶颈（慢 SQL/连接池/Redis）。

## 大数据量检索基线

```powershell
# 造数据（示例：1 万条 FAQ，按需调整）
python -m scripts.seed_perf_data --datasource-id <id> --count 10000
```

> 说明：压测脚本与数据脚本不进入 CI；结果写入上线验收清单（`15-上线验收清单.md`）。
