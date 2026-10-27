# 上线验收：真实后端 HTTP 冒烟报告

- 时间：2026-10-27T20:55:41
- 目标：`http://127.0.0.1:8000`
- 结果：**121/121 通过**；覆盖接口 **44** 个（唯一 method+path）
- 失败：0

| 步骤 | 方法 | 路径 | 期望 | 实际 | 结果 | 耗时(ms) | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| health（根） | GET | `http://127.0.0.1:8000/health` | 200 | 200 | ✅ | 21 |  |
| health（api） | GET | `/health` | 200 | 200 | ✅ | 8 |  |
| 注册用户 验收用户A | POST | `/auth/register` | 201 | 201 | ✅ | 819 |  |
| 登录 验收用户A | POST | `/auth/login` | 200 | 200 | ✅ | 460 |  |
| 当前用户 | GET | `/users/me` | 200 | 200 | ✅ | 43 |  |
| 修改资料 | PATCH | `/users/me` | 200 | 200 | ✅ | 35 |  |
| 修改密码 | POST | `/users/me/password` | 200 | 200 | ✅ | 1053 |  |
| 新密码重新登录 | POST | `/auth/login` | 200 | 200 | ✅ | 495 |  |
| 刷新 token（Cookie） | POST | `/auth/refresh` | 200 | 200 | ✅ | 29 |  |
| 创建数据源 | POST | `/datasources` | 201 | 201 | ✅ | 57 |  |
| 数据源列表 | GET | `/datasources` | 200 | 200 | ✅ | 37 |  |
| 数据源详情 | GET | `/datasources/5d9ed8cc-8c6b-401f-baf4-83b71750fa21` | 200 | 200 | ✅ | 43 |  |
| 更新数据源 | PATCH | `/datasources/5d9ed8cc-8c6b-401f-baf4-83b71750fa21` | 200 | 200 | ✅ | 38 |  |
| 上传文件（CSV） | POST | `/datasources/5d9ed8cc-8c6b-401f-baf4-83b71750fa21/upload` | 202 | 202 | ✅ | 19428 |  |
| 上传后自动清洗: 查询任务 | GET | `/tasks/8cff7102-be29-44f0-91b0-e6d810bf6705` | 200 | 200 | ✅ | 32 |  |
| 上传后自动清洗: 查询任务 | GET | `/tasks/8cff7102-be29-44f0-91b0-e6d810bf6705` | 200 | 200 | ✅ | 19 |  |
| 上传后自动清洗: 查询任务 | GET | `/tasks/8cff7102-be29-44f0-91b0-e6d810bf6705` | 200 | 200 | ✅ | 29 |  |
| 上传后自动清洗: 查询任务 | GET | `/tasks/8cff7102-be29-44f0-91b0-e6d810bf6705` | 200 | 200 | ✅ | 38 |  |
| 上传后自动清洗: 查询任务 | GET | `/tasks/8cff7102-be29-44f0-91b0-e6d810bf6705` | 200 | 200 | ✅ | 25 |  |
| 上传后自动清洗: 查询任务 | GET | `/tasks/8cff7102-be29-44f0-91b0-e6d810bf6705` | 200 | 200 | ✅ | 28 |  |
| 上传后自动清洗: 查询任务 | GET | `/tasks/8cff7102-be29-44f0-91b0-e6d810bf6705` | 200 | 200 | ✅ | 19 |  |
| 上传后自动清洗: 查询任务 | GET | `/tasks/8cff7102-be29-44f0-91b0-e6d810bf6705` | 200 | 200 | ✅ | 42 |  |
| 上传后自动清洗: 查询任务 | GET | `/tasks/8cff7102-be29-44f0-91b0-e6d810bf6705` | 200 | 200 | ✅ | 17 |  |
| 上传后自动清洗: 查询任务 | GET | `/tasks/8cff7102-be29-44f0-91b0-e6d810bf6705` | 200 | 200 | ✅ | 17 |  |
| 上传后自动清洗: 任务终态 | POLL | `/tasks/8cff7102-be29-44f0-91b0-e6d810bf6705` | 200 | 200 | ✅ | 0 |  |
| 触发清洗 | POST | `/datasources/5d9ed8cc-8c6b-401f-baf4-83b71750fa21/clean` | 202/409 | 202 | ✅ | 47 |  |
| 清洗结果列表 | GET | `/datasources/5d9ed8cc-8c6b-401f-baf4-83b71750fa21/cleaned-data` | 200 | 200 | ✅ | 54 |  |
| 清洗结果列表（取首条） | GET | `/datasources/5d9ed8cc-8c6b-401f-baf4-83b71750fa21/cleaned-data` | 200 | 200 | ✅ | 45 |  |
| 清洗结果详情 | GET | `/datasources/5d9ed8cc-8c6b-401f-baf4-83b71750fa21/cleaned-data/91cd3ff1-cc80-4bb8-bf65-51339f46353f` | 200 | 200 | ✅ | 22 |  |
| 提交质量评估 | POST | `/datasources/5d9ed8cc-8c6b-401f-baf4-83b71750fa21/analyze/quality` | 202 | 202 | ✅ | 30 |  |
| 质量评估: 查询任务 | GET | `/tasks/61bb4048-3db0-4e76-9dfd-36e47d56014d` | 200 | 200 | ✅ | 30 |  |
| 质量评估: 查询任务 | GET | `/tasks/61bb4048-3db0-4e76-9dfd-36e47d56014d` | 200 | 200 | ✅ | 30 |  |
| 质量评估: 查询任务 | GET | `/tasks/61bb4048-3db0-4e76-9dfd-36e47d56014d` | 200 | 200 | ✅ | 42 |  |
| 质量评估: 查询任务 | GET | `/tasks/61bb4048-3db0-4e76-9dfd-36e47d56014d` | 200 | 200 | ✅ | 34 |  |
| 质量评估: 查询任务 | GET | `/tasks/61bb4048-3db0-4e76-9dfd-36e47d56014d` | 200 | 200 | ✅ | 27 |  |
| 质量评估: 查询任务 | GET | `/tasks/61bb4048-3db0-4e76-9dfd-36e47d56014d` | 200 | 200 | ✅ | 21 |  |
| 质量评估: 查询任务 | GET | `/tasks/61bb4048-3db0-4e76-9dfd-36e47d56014d` | 200 | 200 | ✅ | 33 |  |
| 质量评估: 查询任务 | GET | `/tasks/61bb4048-3db0-4e76-9dfd-36e47d56014d` | 200 | 200 | ✅ | 32 |  |
| 质量评估: 查询任务 | GET | `/tasks/61bb4048-3db0-4e76-9dfd-36e47d56014d` | 200 | 200 | ✅ | 33 |  |
| 质量评估: 查询任务 | GET | `/tasks/61bb4048-3db0-4e76-9dfd-36e47d56014d` | 200 | 200 | ✅ | 34 |  |
| 质量评估: 查询任务 | GET | `/tasks/61bb4048-3db0-4e76-9dfd-36e47d56014d` | 200 | 200 | ✅ | 18 |  |
| 质量评估: 查询任务 | GET | `/tasks/61bb4048-3db0-4e76-9dfd-36e47d56014d` | 200 | 200 | ✅ | 28 |  |
| 质量评估: 查询任务 | GET | `/tasks/61bb4048-3db0-4e76-9dfd-36e47d56014d` | 200 | 200 | ✅ | 39 |  |
| 质量评估: 查询任务 | GET | `/tasks/61bb4048-3db0-4e76-9dfd-36e47d56014d` | 200 | 200 | ✅ | 37 |  |
| 质量评估: 查询任务 | GET | `/tasks/61bb4048-3db0-4e76-9dfd-36e47d56014d` | 200 | 200 | ✅ | 28 |  |
| 质量评估: 任务终态 | POLL | `/tasks/61bb4048-3db0-4e76-9dfd-36e47d56014d` | 200 | 200 | ✅ | 0 |  |
| 质量评估结果列表 | GET | `/datasources/5d9ed8cc-8c6b-401f-baf4-83b71750fa21/analysis/quality` | 200 | 200 | ✅ | 43 |  |
| 人工复核 | POST | `/datasources/5d9ed8cc-8c6b-401f-baf4-83b71750fa21/analysis/quality/777cc7c0-d47d-4a1f-a4b5-145951dbd547/review` | 200 | 200 | ✅ | 87 |  |
| 提交洞察分析 | POST | `/datasources/5d9ed8cc-8c6b-401f-baf4-83b71750fa21/analyze/insights` | 202 | 202 | ✅ | 29 |  |
| 洞察分析: 查询任务 | GET | `/tasks/282c2944-b8ef-45c1-9c18-a9002bc8a00e` | 200 | 200 | ✅ | 31 |  |
| 洞察分析: 查询任务 | GET | `/tasks/282c2944-b8ef-45c1-9c18-a9002bc8a00e` | 200 | 200 | ✅ | 34 |  |
| 洞察分析: 查询任务 | GET | `/tasks/282c2944-b8ef-45c1-9c18-a9002bc8a00e` | 200 | 200 | ✅ | 29 |  |
| 洞察分析: 查询任务 | GET | `/tasks/282c2944-b8ef-45c1-9c18-a9002bc8a00e` | 200 | 200 | ✅ | 31 |  |
| 洞察分析: 查询任务 | GET | `/tasks/282c2944-b8ef-45c1-9c18-a9002bc8a00e` | 200 | 200 | ✅ | 28 |  |
| 洞察分析: 任务终态 | POLL | `/tasks/282c2944-b8ef-45c1-9c18-a9002bc8a00e` | 200 | 200 | ✅ | 0 |  |
| 洞察结果 | GET | `/datasources/5d9ed8cc-8c6b-401f-baf4-83b71750fa21/analysis/insights` | 200/404 | 200 | ✅ | 33 |  |
| 提交知识提取 | POST | `/datasources/5d9ed8cc-8c6b-401f-baf4-83b71750fa21/extract-knowledge` | 202 | 202 | ✅ | 19 |  |
| 知识提取: 查询任务 | GET | `/tasks/b8f0ccbd-1397-4473-a84b-b8f454e74bac` | 200 | 200 | ✅ | 13 |  |
| 知识提取: 查询任务 | GET | `/tasks/b8f0ccbd-1397-4473-a84b-b8f454e74bac` | 200 | 200 | ✅ | 29 |  |
| 知识提取: 查询任务 | GET | `/tasks/b8f0ccbd-1397-4473-a84b-b8f454e74bac` | 200 | 200 | ✅ | 25 |  |
| 知识提取: 查询任务 | GET | `/tasks/b8f0ccbd-1397-4473-a84b-b8f454e74bac` | 200 | 200 | ✅ | 37 |  |
| 知识提取: 查询任务 | GET | `/tasks/b8f0ccbd-1397-4473-a84b-b8f454e74bac` | 200 | 200 | ✅ | 19 |  |
| 知识提取: 查询任务 | GET | `/tasks/b8f0ccbd-1397-4473-a84b-b8f454e74bac` | 200 | 200 | ✅ | 15 |  |
| 知识提取: 查询任务 | GET | `/tasks/b8f0ccbd-1397-4473-a84b-b8f454e74bac` | 200 | 200 | ✅ | 42 |  |
| 知识提取: 查询任务 | GET | `/tasks/b8f0ccbd-1397-4473-a84b-b8f454e74bac` | 200 | 200 | ✅ | 17 |  |
| 知识提取: 查询任务 | GET | `/tasks/b8f0ccbd-1397-4473-a84b-b8f454e74bac` | 200 | 200 | ✅ | 40 |  |
| 知识提取: 查询任务 | GET | `/tasks/b8f0ccbd-1397-4473-a84b-b8f454e74bac` | 200 | 200 | ✅ | 36 |  |
| 知识提取: 查询任务 | GET | `/tasks/b8f0ccbd-1397-4473-a84b-b8f454e74bac` | 200 | 200 | ✅ | 33 |  |
| 知识提取: 查询任务 | GET | `/tasks/b8f0ccbd-1397-4473-a84b-b8f454e74bac` | 200 | 200 | ✅ | 16 |  |
| 知识提取: 查询任务 | GET | `/tasks/b8f0ccbd-1397-4473-a84b-b8f454e74bac` | 200 | 200 | ✅ | 21 |  |
| 知识提取: 查询任务 | GET | `/tasks/b8f0ccbd-1397-4473-a84b-b8f454e74bac` | 200 | 200 | ✅ | 34 |  |
| 知识提取: 查询任务 | GET | `/tasks/b8f0ccbd-1397-4473-a84b-b8f454e74bac` | 200 | 200 | ✅ | 21 |  |
| 知识提取: 查询任务 | GET | `/tasks/b8f0ccbd-1397-4473-a84b-b8f454e74bac` | 200 | 200 | ✅ | 18 |  |
| 知识提取: 查询任务 | GET | `/tasks/b8f0ccbd-1397-4473-a84b-b8f454e74bac` | 200 | 200 | ✅ | 33 |  |
| 知识提取: 查询任务 | GET | `/tasks/b8f0ccbd-1397-4473-a84b-b8f454e74bac` | 200 | 200 | ✅ | 20 |  |
| 知识提取: 查询任务 | GET | `/tasks/b8f0ccbd-1397-4473-a84b-b8f454e74bac` | 200 | 200 | ✅ | 21 |  |
| 知识提取: 查询任务 | GET | `/tasks/b8f0ccbd-1397-4473-a84b-b8f454e74bac` | 200 | 200 | ✅ | 22 |  |
| 知识提取: 查询任务 | GET | `/tasks/b8f0ccbd-1397-4473-a84b-b8f454e74bac` | 200 | 200 | ✅ | 31 |  |
| 知识提取: 查询任务 | GET | `/tasks/b8f0ccbd-1397-4473-a84b-b8f454e74bac` | 200 | 200 | ✅ | 42 |  |
| 知识提取: 任务终态 | POLL | `/tasks/b8f0ccbd-1397-4473-a84b-b8f454e74bac` | 200 | 200 | ✅ | 0 |  |
| FAQ 列表 | GET | `/datasources/5d9ed8cc-8c6b-401f-baf4-83b71750fa21/knowledge/faq` | 200 | 200 | ✅ | 44 |  |
| 知识盲区 | GET | `/datasources/5d9ed8cc-8c6b-401f-baf4-83b71750fa21/knowledge/gaps` | 200 | 200 | ✅ | 31 |  |
| 知识检索 | GET | `/datasources/5d9ed8cc-8c6b-401f-baf4-83b71750fa21/knowledge/search` | 200 | 200 | ✅ | 14492 |  |
| 手动新增 FAQ | POST | `/datasources/5d9ed8cc-8c6b-401f-baf4-83b71750fa21/knowledge/faq` | 201 | 201 | ✅ | 73 |  |
| 更新 FAQ | PATCH | `/datasources/5d9ed8cc-8c6b-401f-baf4-83b71750fa21/knowledge/faq/17c92ac6-f4d1-4334-af03-490c8ec80119` | 200 | 200 | ✅ | 43 |  |
| 删除 FAQ | DELETE | `/datasources/5d9ed8cc-8c6b-401f-baf4-83b71750fa21/knowledge/faq/17c92ac6-f4d1-4334-af03-490c8ec80119` | 204 | 204 | ✅ | 49 |  |
| 创建报告 | POST | `/datasources/5d9ed8cc-8c6b-401f-baf4-83b71750fa21/reports` | 202 | 202 | ✅ | 57 |  |
| 报告详情 | GET | `/reports/1d7c4ac5-2961-4ca8-ae45-78ac66475993` | 200 | 200 | ✅ | 46 |  |
| 报告详情 | GET | `/reports/1d7c4ac5-2961-4ca8-ae45-78ac66475993` | 200 | 200 | ✅ | 29 |  |
| 报告详情 | GET | `/reports/1d7c4ac5-2961-4ca8-ae45-78ac66475993` | 200 | 200 | ✅ | 32 |  |
| 报告详情 | GET | `/reports/1d7c4ac5-2961-4ca8-ae45-78ac66475993` | 200 | 200 | ✅ | 17 |  |
| 报告详情 | GET | `/reports/1d7c4ac5-2961-4ca8-ae45-78ac66475993` | 200 | 200 | ✅ | 41 |  |
| 报告详情 | GET | `/reports/1d7c4ac5-2961-4ca8-ae45-78ac66475993` | 200 | 200 | ✅ | 19 |  |
| 报告详情 | GET | `/reports/1d7c4ac5-2961-4ca8-ae45-78ac66475993` | 200 | 200 | ✅ | 17 |  |
| 报告详情 | GET | `/reports/1d7c4ac5-2961-4ca8-ae45-78ac66475993` | 200 | 200 | ✅ | 26 |  |
| 报告详情 | GET | `/reports/1d7c4ac5-2961-4ca8-ae45-78ac66475993` | 200 | 200 | ✅ | 28 |  |
| 报告详情 | GET | `/reports/1d7c4ac5-2961-4ca8-ae45-78ac66475993` | 200 | 200 | ✅ | 42 |  |
| 报告详情 | GET | `/reports/1d7c4ac5-2961-4ca8-ae45-78ac66475993` | 200 | 200 | ✅ | 28 |  |
| 报告详情 | GET | `/reports/1d7c4ac5-2961-4ca8-ae45-78ac66475993` | 200 | 200 | ✅ | 18 |  |
| 报告详情 | GET | `/reports/1d7c4ac5-2961-4ca8-ae45-78ac66475993` | 200 | 200 | ✅ | 29 |  |
| 报告详情 | GET | `/reports/1d7c4ac5-2961-4ca8-ae45-78ac66475993` | 200 | 200 | ✅ | 29 |  |
| 报告终态 | POLL | `/reports/1d7c4ac5-2961-4ca8-ae45-78ac66475993` | 200 | 200 | ✅ | 0 | completed |
| 报告列表 | GET | `/datasources/5d9ed8cc-8c6b-401f-baf4-83b71750fa21/reports` | 200 | 200 | ✅ | 30 |  |
| 报告下载 | GET | `/reports/1d7c4ac5-2961-4ca8-ae45-78ac66475993/download` | 200 | 200 | ✅ | 40 |  |
| 删除报告 | DELETE | `/reports/1d7c4ac5-2961-4ca8-ae45-78ac66475993` | 200/204 | 204 | ✅ | 31 |  |
| 任务列表 | GET | `/tasks` | 200 | 200 | ✅ | 21 |  |
| 任务详情 | GET | `/tasks/8cff7102-be29-44f0-91b0-e6d810bf6705` | 200 | 200 | ✅ | 24 |  |
| 取消已完成任务 | POST | `/tasks/8cff7102-be29-44f0-91b0-e6d810bf6705/cancel` | 200/409 | 409 | ✅ | 14 |  |
| 重试任务 | POST | `/tasks/8cff7102-be29-44f0-91b0-e6d810bf6705/retry` | 200/409 | 409 | ✅ | 28 |  |
| 任务 SSE 首帧 | GET | `/tasks/stream` | 200 | 200 | ✅ | 0 | data: {"items": [{"id": "b8f0ccbd-1397-4473-a84b-b8f454e74bac", "task_type": "extract", "status": "completed", "progress |
| 401 无 token | GET | `/users/me` | 401 | 401 | ✅ | 19 |  |
| 409 重复注册 | POST | `/auth/register` | 409 | 409 | ✅ | 20 |  |
| 404 数据源不存在 | GET | `/datasources/16a2775f-8261-41df-8ff8-f16300fc0058` | 404 | 404 | ✅ | 25 |  |
| 422 参数校验 | POST | `/datasources` | 422 | 422 | ✅ | 27 |  |
| 415 扩展名不支持 | POST | `/datasources/5d9ed8cc-8c6b-401f-baf4-83b71750fa21/upload` | 415 | 415 | ✅ | 28 |  |
| 413 文件超限 | POST | `/datasources/5d9ed8cc-8c6b-401f-baf4-83b71750fa21/upload` | 413 | 413 | ✅ | 507 |  |
| 注册用户 验收用户B | POST | `/auth/register` | 201 | 201 | ✅ | 320 |  |
| 登录 验收用户B | POST | `/auth/login` | 200 | 200 | ✅ | 276 |  |
| 403 越权访问他人数据源 | GET | `/datasources/5d9ed8cc-8c6b-401f-baf4-83b71750fa21` | 403 | 403 | ✅ | 19 |  |
| 清理：物理删除数据源 | DELETE | `/datasources/5d9ed8cc-8c6b-401f-baf4-83b71750fa21` | 200/204 | 200 | ✅ | 48 |  |
| 退出登录 | POST | `/auth/logout` | 200/204 | 200 | ✅ | 27 |  |

> 未纳入本脚本的错误码：429（需开启限流后单独验证）、500/503（需故障注入，已由单测/异常处理覆盖）。
