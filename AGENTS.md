# AGENTS.md

> 给 AI 编码助手（Claude Code / Cursor / OpenCode 等）和新人的仓库说明。
> 只放**无密钥**的规范与流程；账号、服务器路径、密钥位置在本地 `OPS-CHEATSHEET.local.md`（不提交）。

## 这是什么

AI 客服数据分析平台：上传对话/音视频 → AI 清洗 → 质量评估 → 知识提取 → 洞察 → 报告。
后端 FastAPI + Celery，前端 React，存储 PostgreSQL(pgvector) / Redis / MinIO。

## 目录与分层（**最重要**）

依赖方向严格单向，越界 CI 会失败：

```
api → tasks → services → application → agents → repositories → ports → models → schemas → core
                     ↑
              app/composition（组合根，不在栈内）
```

| 目录 | 职责 | 不要做 |
| --- | --- | --- |
| `app/api/` | 路由、JWT/RBAC、BYOK 守门、分页参数解析 | 直接写库、直接 import `tasks` |
| `app/tasks/` | Celery 入口，转发给 service | 放业务逻辑 |
| `app/services/` | 用例编排、事务边界（`flush`）、归属校验 | 持有 Celery 任务对象、写裸 SQL |
| `app/application/` | 无框架细节的管线（转写、内容路由、取消查询） | 依赖 services / FastAPI |
| `app/agents/` | LLM 能力（BYOK、重试、成本、降级、结构化输出） | 依赖 services |
| `app/repositories/` | SQL 唯一入口（含分页执行） | 放业务规则 |
| `app/ports/` | 抽象接口（`LLMPort` / `TranscriberPort` / `CredentialPort`） | 依赖实现层、写厂商细节 |
| `app/models/` `app/schemas/` | ORM 实体 / Pydantic DTO | 依赖上层 |
| `app/core/` | 配置、DB、安全、错误码、Redis、成本、降级 | 依赖业务层 |
| `app/composition/` | 组合根：`executors`（任务类型→执行器）、`enqueue`（唯一 `.delay()` 的地方） | 被 services import |

**5 条 CI 契约**（`backend/.importlinter`）：`declared-layers` / `http-layer-not-depended-on` /
`data-layer-is-leaf` / `ports-are-inner` / `repositories-are-inner`。
现存欠账 3 条（`core → models/schemas`）已逐条登记在 `ignore_imports`，**修掉一条就删一行**。

## 常用命令

```bash
# 后端（在 backend/ 下，用 backend/venv）
pytest -m "not prompt"          # 全量（645 条，跳过需要真实 Key 的 prompt 用例）
pytest tests/unit -q            # 单测
black app tests && flake8 app tests && mypy app
lint-imports                    # 分层契约

# 前端（在 frontend/ 下）
npm run lint
npm run test:coverage
npm run build
```

## 改代码的硬规则

1. **写库**：`api/` 与 `application/` 层禁止 `session.add/delete`，改用 `app.repositories`（CI 有 grep 门禁）。
2. **新外部依赖**：先定 `app/ports/` 的 Protocol，实现放 service 侧，用构造参数注入；不要在业务代码里直接 import 具体实现。
3. **入队**：只在 `app/composition/enqueue.py` 调 `.delay()`；service 只建任务行 + 改状态。
4. **新增数据访问**：加到对应 repository，不要把 SQL 写回 service。
5. **错误**：抛 `app/core/exceptions.py` 里的领域异常（统一错误码），不要裸 `ValueError`。
6. **只搬 SQL，不搬规则**：去重策略、状态机、归属校验留在原层。

## CI 与合并

- `main` 受保护：必需检查 `后端测试`、`前端测试`（`enforce_admins`），所有改动走 PR。
- `test.yml` 有 `changes` job（`dorny/paths-filter`）：只改 `docs/**` 时两个测试 job 为 skipped（约 10 秒）。
- **不要**给 workflow 加 workflow 级 `paths-ignore`：required check 不会产生，PR 会卡在 `Expected`。
- E2E（`e2e.yml`）用 workflow 级 `paths`（`frontend/**` / `backend/**` / `nginx/**`），非必需检查。
- 文档 PR 不需要跑全量测试；改了 `backend/**` 或 `frontend/**` 会正常跑。

## 部署与发布

- 部署细节见 `docs/04-development/14-部署与运维手册.md`（含热补丁、pip 镜像源、nginx 重启）。
- 云端 compose 与仓库**不一致**，禁止整体覆盖；只改需要改的行。
- `nginx/**` 改动要重建前端镜像（配置是 `COPY` 进镜像的），`docker cp` 只是临时生效。
- Blog：仓库 `my-resume`，文章放 `src/content/posts/*.md`，`npm run build` 预检，push `main` 即发布到 https://foolgone.github.io/blog/

## 已知陷阱

| 陷阱 | 说明 |
| --- | --- |
| `docker commit` 吞 entrypoint | 用 `--entrypoint sleep` 起的容器直接 commit，镜像 ENTRYPOINT 会变成 `sleep`；必须 `--change` 改回 |
| 部署脚本不同步源码 | `unified_deploy.py cloud` 只重建镜像、不覆盖宿主机 `/opt/ai-insight-hub/backend`；2026-11-13 因此把坏代码又构建了一遍。**构建前先 `grep` 确认修复已进源码**；VM 上没有 `rsync`，用 `tar -xzf ... -C /root/ai-insight-hub --overwrite` |
| `docker cp` 静默失败 | 热补丁脚本里 `docker cp` 失败不报错也不中断，三个容器可能仍是旧代码。**部署后必须在容器内 `grep -c <新符号>` 验证**，别只看 api health |
| api 重建后 502 | nginx 缓存上游 IP，需 `restart nginx` |
| 云端全量构建极慢 | 直连 pypi 约 19 kB/s；Dockerfile 默认已用腾讯云镜像 |
| `acks_late` 重投递 | 只对 `clean` 任务开启；已 `completed` 的任务会短路（`redelivered: true`） |
| 单声道记录 | `ai_response` 为空 → 不参与质量评估，但仍可用于知识提取/洞察 |
| `runtime_checkable` | 只校验方法名存在，**不校验签名**；签名一致性靠 mypy |

## 文档索引

| 文档 | 内容 |
| --- | --- |
| `docs/03-architecture/01-系统架构.md` | 系统总览 |
| `docs/03-architecture/06-分层架构图.svg` | 分层 + 契约 + 调用链 |
| `docs/03-architecture/07-参考架构评估.md` | 与参考架构的对照与采纳清单 |
| `docs/04-development/14-部署与运维手册.md` | 部署、热补丁、nginx、pip 源 |
| `docs/04-development/20-内容路由与架构分层计划.md` | 分层改造实施记录 |
