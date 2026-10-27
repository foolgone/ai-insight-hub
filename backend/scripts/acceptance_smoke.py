"""上线验收：真实后端 HTTP 冒烟（39 个 `/api/v1` 端点 + 错误码）。

用途（15-上线验收清单 §8.1/§2）：
- 对**真实运行**的 API（uvicorn + Celery worker + PG/Redis）逐端点发请求；
- 覆盖认证、数据源、上传→清洗、质量评估、洞察、知识库、报告、任务（含 SSE）；
- 覆盖可触发的错误码：401/403/404/409/413/415/422；
- 429/500/503 需独立环境（限流开启 / 故障注入），本脚本单独标注。

运行（backend 目录，需 API 与 worker 已启动）：
    .\\venv\\Scripts\\python.exe scripts\\acceptance_smoke.py
可选参数：
    --base-url http://127.0.0.1:8000
    --report  ops/acceptance/smoke-report.md

说明：会真实调用 LLM（清洗/评估/提取/洞察/报告各 1 次），产生少量费用；
数据源与报告会在结束时清理，测试用户保留（无删除用户接口）。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

TIMEOUT = httpx.Timeout(180.0, connect=10.0)


@dataclass
class Step:
    name: str
    method: str
    path: str
    expected: tuple[int, ...]
    status: int
    ok: bool
    note: str = ""
    elapsed_ms: int = 0


@dataclass
class Smoke:
    client: httpx.Client
    api_base: str = "http://127.0.0.1:8000/api/v1"
    steps: list[Step] = field(default_factory=list)
    endpoints: set[tuple[str, str]] = field(default_factory=set)

    def call(
        self,
        name: str,
        method: str,
        path: str,
        expected: tuple[int, ...] | int,
        *,
        json_body: Any = None,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        files: Any = None,
        content: bytes | None = None,
        fatal: bool = False,
        absolute: bool = False,
    ) -> httpx.Response | None:
        expected_tuple = expected if isinstance(expected, tuple) else (expected,)
        url = path if absolute else f"{self.api_base}{path}"
        started = time.perf_counter()
        try:
            response = self.client.request(
                method,
                url,
                json=json_body,
                headers=headers,
                params=params,
                files=files,
                content=content,
            )
        except Exception as exc:  # noqa: BLE001 - 记录后由调用方决定是否致命
            self.steps.append(
                Step(name, method, path, expected_tuple, 0, False, f"{type(exc).__name__}: {exc}")
            )
            print(f"[FAIL] {name} {method} {path} -> {type(exc).__name__}: {exc}")
            if fatal:
                raise
            return None
        elapsed = int((time.perf_counter() - started) * 1000)
        ok = response.status_code in expected_tuple
        note = ""
        if not ok:
            note = response.text[:300].replace("\n", " ")
        self.endpoints.add(
            (method.upper(), path.split("?")[0] if absolute else path.split("?")[0])
        )
        self.steps.append(
            Step(name, method, path, expected_tuple, response.status_code, ok, note, elapsed)
        )
        flag = "OK  " if ok else "FAIL"
        print(f"[{flag}] {name:<38} {method:<6} {path:<62} {response.status_code}")
        if fatal and not ok:
            raise SystemExit(f"致命步骤失败：{name} -> {response.status_code} {note}")
        return response

    def json(self, response: httpx.Response | None) -> dict[str, Any]:
        if response is None:
            return {}
        try:
            data = response.json()
        except ValueError:
            return {}
        return data if isinstance(data, dict) else {"_list": data}


def wait_task(
    smoke: Smoke, task_id: str, label: str, headers: dict[str, str], timeout_s: int = 180
) -> str:
    """轮询任务直到终态，返回最终 status。"""
    deadline = time.time() + timeout_s
    status = "unknown"
    last: dict[str, Any] = {}
    while time.time() < deadline:
        response = smoke.call(
            f"{label}: 查询任务", "GET", f"/tasks/{task_id}", 200, headers=headers
        )
        last = smoke.json(response)
        status = str(last.get("status") or "unknown")
        if status in {"completed", "failed", "cancelled"}:
            break
        time.sleep(2)
    if status != "completed":
        error = str(last.get("error_message") or "")[:200]
        smoke.steps.append(
            Step(
                f"{label}: 任务终态",
                "POLL",
                f"/tasks/{task_id}",
                (200,),
                0,
                False,
                f"status={status} error={error}",
            )
        )
        print(f"[FAIL] {label} 任务终态 status={status} error={error}")
    else:
        smoke.steps.append(Step(f"{label}: 任务终态", "POLL", f"/tasks/{task_id}", (200,), 200, True))
    return status


def register_login(smoke: Smoke, email: str, password: str, name: str) -> str:
    smoke.call(
        f"注册用户 {name}",
        "POST",
        "/auth/register",
        201,
        json_body={"email": email, "password": password, "name": name},
        fatal=True,
    )
    login = smoke.call(
        f"登录 {name}",
        "POST",
        "/auth/login",
        200,
        json_body={"email": email, "password": password},
        fatal=True,
    )
    return str(smoke.json(login).get("access_token") or "")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--report", default="ops/acceptance/smoke-report.md")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    suffix = datetime.now().strftime("%H%M%S")
    email = f"accept-{suffix}@example.com"
    password = "Accept12345"
    new_password = "Accept67890"

    smoke = Smoke(
        client=httpx.Client(timeout=TIMEOUT, follow_redirects=True),
        api_base=f"{base}/api/v1",
    )

    # ---------- 0. 系统级 ----------
    smoke.call("health（根）", "GET", f"{base}/health", 200, absolute=True)
    smoke.call("health（api）", "GET", "/health", 200)

    # ---------- 1. 认证 ----------
    token = register_login(smoke, email, password, "验收用户A")
    auth = {"Authorization": f"Bearer {token}"}
    smoke.call("当前用户", "GET", "/users/me", 200, headers=auth)
    smoke.call("修改资料", "PATCH", "/users/me", 200, headers=auth, json_body={"name": "验收用户A2"})
    smoke.call(
        "修改密码",
        "POST",
        "/users/me/password",
        200,
        headers=auth,
        json_body={"current_password": password, "new_password": new_password},
    )
    relogin = smoke.call(
        "新密码重新登录",
        "POST",
        "/auth/login",
        200,
        json_body={"email": email, "password": new_password},
    )
    auth = {"Authorization": f"Bearer {smoke.json(relogin).get('access_token') or ''}"}
    smoke.call("刷新 token（Cookie）", "POST", "/auth/refresh", 200, headers=auth, json_body={})

    # ---------- 2. 数据源 ----------
    created = smoke.call(
        "创建数据源",
        "POST",
        "/datasources",
        201,
        headers=auth,
        json_body={"name": f"验收数据源-{suffix}", "type": "customer_service"},
    )
    datasource_id = str(smoke.json(created).get("id") or "")
    smoke.call("数据源列表", "GET", "/datasources", 200, headers=auth)
    smoke.call("数据源详情", "GET", f"/datasources/{datasource_id}", 200, headers=auth)
    smoke.call(
        "更新数据源",
        "PATCH",
        f"/datasources/{datasource_id}",
        200,
        headers=auth,
        json_body={"description": "验收脚本创建"},
    )

    # ---------- 3. 上传 → 自动清洗 ----------
    csv_content = "客户,客服\n怎么退款？,7 天可申请退款。\n多久发货？,48 小时内发出。\n".encode()
    uploaded = smoke.call(
        "上传文件（CSV）",
        "POST",
        f"/datasources/{datasource_id}/upload",
        202,
        headers=auth,
        files={"file": ("acceptance.csv", csv_content, "text/csv")},
    )
    upload_task = str(smoke.json(uploaded).get("task_id") or "")
    if upload_task:
        wait_task(smoke, upload_task, "上传后自动清洗", auth)

    smoke.call("触发清洗", "POST", f"/datasources/{datasource_id}/clean", (202, 409), headers=auth)
    smoke.call("清洗结果列表", "GET", f"/datasources/{datasource_id}/cleaned-data", 200, headers=auth)
    cleaned = smoke.call(
        "清洗结果列表（取首条）",
        "GET",
        f"/datasources/{datasource_id}/cleaned-data",
        200,
        headers=auth,
        params={"page": 1, "limit": 5},
    )
    items = smoke.json(cleaned).get("items") or []
    if items:
        smoke.call(
            "清洗结果详情",
            "GET",
            f"/datasources/{datasource_id}/cleaned-data/{items[0]['id']}",
            200,
            headers=auth,
        )

    # ---------- 4. 质量评估 ----------
    eval_resp = smoke.call(
        "提交质量评估",
        "POST",
        f"/datasources/{datasource_id}/analyze/quality",
        202,
        headers=auth,
        json_body={"data_ids": [], "config": {}},
    )
    eval_task = str(smoke.json(eval_resp).get("task_id") or "")
    if eval_task:
        wait_task(smoke, eval_task, "质量评估", auth)
    quality = smoke.call(
        "质量评估结果列表", "GET", f"/datasources/{datasource_id}/analysis/quality", 200, headers=auth
    )
    quality_items = smoke.json(quality).get("items") or []
    if quality_items:
        result_id = quality_items[0].get("id") or quality_items[0].get("result_id")
        if result_id:
            smoke.call(
                "人工复核",
                "POST",
                f"/datasources/{datasource_id}/analysis/quality/{result_id}/review",
                200,
                headers=auth,
                json_body={"decision": "approved", "note": "验收脚本复核"},
            )

    # ---------- 5. 洞察 ----------
    insight_resp = smoke.call(
        "提交洞察分析",
        "POST",
        f"/datasources/{datasource_id}/analyze/insights",
        202,
        headers=auth,
        json_body={"config": {}},
    )
    insight_task = str(smoke.json(insight_resp).get("task_id") or "")
    if insight_task:
        wait_task(smoke, insight_task, "洞察分析", auth)
    smoke.call("洞察结果", "GET", f"/datasources/{datasource_id}/analysis/insights", (200, 404), headers=auth)

    # ---------- 6. 知识库 ----------
    extract_resp = smoke.call(
        "提交知识提取",
        "POST",
        f"/datasources/{datasource_id}/extract-knowledge",
        202,
        headers=auth,
        json_body={},
    )
    extract_task = str(smoke.json(extract_resp).get("task_id") or "")
    if extract_task:
        wait_task(smoke, extract_task, "知识提取", auth)
    smoke.call("FAQ 列表", "GET", f"/datasources/{datasource_id}/knowledge/faq", 200, headers=auth)
    smoke.call("知识盲区", "GET", f"/datasources/{datasource_id}/knowledge/gaps", 200, headers=auth)
    smoke.call(
        "知识检索",
        "GET",
        f"/datasources/{datasource_id}/knowledge/search",
        200,
        headers=auth,
        params={"q": "退款"},
    )
    faq = smoke.call(
        "手动新增 FAQ",
        "POST",
        f"/datasources/{datasource_id}/knowledge/faq",
        201,
        headers=auth,
        json_body={"question": f"验收 FAQ {suffix}", "answer": "验收答案", "category": "验收"},
    )
    faq_id = str(smoke.json(faq).get("id") or "")
    if faq_id:
        smoke.call(
            "更新 FAQ",
            "PATCH",
            f"/datasources/{datasource_id}/knowledge/faq/{faq_id}",
            200,
            headers=auth,
            json_body={"answer": "验收答案（已更新）"},
        )
        smoke.call(
            "删除 FAQ",
            "DELETE",
            f"/datasources/{datasource_id}/knowledge/faq/{faq_id}",
            204,
            headers=auth,
        )

    # ---------- 7. 报告 ----------
    report_resp = smoke.call(
        "创建报告",
        "POST",
        f"/datasources/{datasource_id}/reports",
        202,
        headers=auth,
        json_body={
            "title": f"验收报告-{suffix}",
            "report_type": "quality",
            "format": "markdown",
            "config": {},
        },
    )
    report_id = str(smoke.json(report_resp).get("id") or "")
    if report_id:
        deadline = time.time() + 180
        report_status = "unknown"
        while time.time() < deadline:
            detail = smoke.call("报告详情", "GET", f"/reports/{report_id}", 200, headers=auth)
            report_status = str(smoke.json(detail).get("status") or "")
            if report_status in {"completed", "failed"}:
                break
            time.sleep(2)
        smoke.steps.append(
            Step("报告终态", "POLL", f"/reports/{report_id}", (200,), 200, report_status == "completed", report_status)
        )
        print(f"[{'OK  ' if report_status == 'completed' else 'FAIL'}] 报告终态 status={report_status}")
        smoke.call("报告列表", "GET", f"/datasources/{datasource_id}/reports", 200, headers=auth)
        if report_status == "completed":
            smoke.call("报告下载", "GET", f"/reports/{report_id}/download", 200, headers=auth)
        smoke.call("删除报告", "DELETE", f"/reports/{report_id}", (200, 204), headers=auth)

    # ---------- 8. 任务 ----------
    smoke.call("任务列表", "GET", "/tasks", 200, headers=auth)
    if upload_task:
        smoke.call("任务详情", "GET", f"/tasks/{upload_task}", 200, headers=auth)
        smoke.call("取消已完成任务", "POST", f"/tasks/{upload_task}/cancel", (200, 409), headers=auth)
        smoke.call("重试任务", "POST", f"/tasks/{upload_task}/retry", (200, 409), headers=auth)
    try:
        with smoke.client.stream(
            "GET",
            f"{base}/api/v1/tasks/stream",
            headers=auth,
            timeout=httpx.Timeout(10.0),
        ) as stream:
            first_line = ""
            for line in stream.iter_lines():
                if line.startswith("data:"):
                    first_line = line[:200]
                    break
        ok = bool(first_line)
        smoke.endpoints.add(("GET", "/tasks/stream"))
        smoke.steps.append(
            Step("任务 SSE 首帧", "GET", "/tasks/stream", (200,), 200, ok, first_line[:120])
        )
        print(f"[{'OK  ' if ok else 'FAIL'}] 任务 SSE 首帧 {first_line[:80]}")
    except Exception as exc:  # noqa: BLE001
        smoke.steps.append(
            Step("任务 SSE 首帧", "GET", "/tasks/stream", (200,), 0, False, f"{type(exc).__name__}: {exc}")
        )
        print(f"[FAIL] 任务 SSE 首帧 {type(exc).__name__}: {exc}")

    # ---------- 9. 错误码（可触发项） ----------
    smoke.call("401 无 token", "GET", "/users/me", 401)
    smoke.call(
        "409 重复注册",
        "POST",
        "/auth/register",
        409,
        json_body={"email": email, "password": password, "name": "重复"},
    )
    smoke.call("404 数据源不存在", "GET", f"/datasources/{uuid.uuid4()}", 404, headers=auth)
    smoke.call(
        "422 参数校验",
        "POST",
        "/datasources",
        422,
        headers=auth,
        json_body={"type": "customer_service"},
    )
    smoke.call(
        "415 扩展名不支持",
        "POST",
        f"/datasources/{datasource_id}/upload",
        415,
        headers=auth,
        files={"file": ("bad.exe", b"MZ", "application/octet-stream")},
    )
    smoke.call(
        "413 文件超限",
        "POST",
        f"/datasources/{datasource_id}/upload",
        413,
        headers=auth,
        files={"file": ("big.csv", b"0" * (51 * 1024 * 1024), "text/csv")},
    )

    other_email = f"accept-b-{suffix}@example.com"
    register_login(smoke, other_email, password, "验收用户B")
    other_login = smoke.client.post(
        f"{base}/api/v1/auth/login", json={"email": other_email, "password": password}
    )
    other_token = str(smoke.json(other_login).get("access_token") or "")
    smoke.call(
        "403 越权访问他人数据源",
        "GET",
        f"/datasources/{datasource_id}",
        403,
        headers={"Authorization": f"Bearer {other_token}"},
    )

    # ---------- 10. 退出 + 清理 ----------
    smoke.call(
        "清理：物理删除数据源",
        "DELETE",
        f"/datasources/{datasource_id}",
        (200, 204),
        headers=auth,
        params={"force": "true"},
    )
    smoke.call("退出登录", "POST", "/auth/logout", (200, 204), headers=auth, json_body={})

    # ---------- 汇总 ----------
    total = len(smoke.steps)
    passed = sum(1 for item in smoke.steps if item.ok)
    failed = [item for item in smoke.steps if not item.ok]
    coverage = len(smoke.endpoints)

    print("\n" + "=" * 100)
    print(f"步骤：{passed}/{total} 通过；覆盖接口：{coverage} 个（唯一 method+path）")
    if failed:
        print("失败步骤：")
        for item in failed:
            print(f"  - {item.name} -> {item.status} {item.note}")
    print("=" * 100)

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 上线验收：真实后端 HTTP 冒烟报告",
        "",
        f"- 时间：{datetime.now().isoformat(timespec='seconds')}",
        f"- 目标：`{base}`",
        f"- 结果：**{passed}/{total} 通过**；覆盖接口 **{coverage}** 个（唯一 method+path）",
        f"- 失败：{len(failed)}",
        "",
        "| 步骤 | 方法 | 路径 | 期望 | 实际 | 结果 | 耗时(ms) | 备注 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in smoke.steps:
        expected = "/".join(str(code) for code in item.expected)
        note = item.note.replace("|", "\\|") if item.note else ""
        lines.append(
            f"| {item.name} | {item.method} | `{item.path}` | {expected} | {item.status} | "
            f"{'✅' if item.ok else '❌'} | {item.elapsed_ms} | {note} |"
        )
    lines.append("")
    lines.append("> 未纳入本脚本的错误码：429（需开启限流后单独验证）、500/503（需故障注入，已由单测/异常处理覆盖）。")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"报告已写入：{report_path.resolve()}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
