"""B-701 性能测试脚本（Locust）。

运行（需先启动后端与依赖）：
```powershell
pip install locust
$env:LOAD_TEST_EMAIL = "loadtest@example.com"
$env:LOAD_TEST_PASSWORD = "secret123"
locust -f tests/load/locustfile.py --host http://127.0.0.1:8000 --headless -u 100 -r 10 -t 3m
```

验收口径（计划 B-701）：
- 100 并发下 P95 < 2s（健康检查/列表/检索）；
- 1 万/10 万向量检索 P95 目标见 `tests/load/README.md`；
- 成本符合预算（llm_calls 聚合对账）。
"""
from __future__ import annotations

import os

from locust import HttpUser, between, task

EMAIL = os.getenv("LOAD_TEST_EMAIL", "loadtest@example.com")
PASSWORD = os.getenv("LOAD_TEST_PASSWORD", "secret123")


class AIInsightUser(HttpUser):
    wait_time = between(0.5, 1.5)
    token: str | None = None
    datasource_id: str | None = None

    def on_start(self) -> None:
        login = self.client.post(
            "/api/v1/auth/login",
            json={"email": EMAIL, "password": PASSWORD},
        )
        if login.status_code == 200:
            self.token = login.json()["access_token"]
            datasources = self.client.get(
                "/api/v1/datasources",
                headers=self._headers(),
            )
            if datasources.status_code == 200:
                items = datasources.json().get("items") or []
                if items:
                    self.datasource_id = items[0]["id"]

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    @task(5)
    def health(self) -> None:
        self.client.get("/health")

    @task(3)
    def list_datasources(self) -> None:
        self.client.get("/api/v1/datasources?page=1&limit=20", headers=self._headers())

    @task(2)
    def list_tasks(self) -> None:
        self.client.get("/api/v1/tasks?page=1&limit=20", headers=self._headers())

    @task(2)
    def search_knowledge(self) -> None:
        if not self.datasource_id:
            return
        self.client.get(
            f"/api/v1/datasources/{self.datasource_id}/knowledge/search",
            params={"q": "退货", "limit": 10, "threshold": 0.3},
            headers=self._headers(),
        )

    @task(1)
    def list_reports(self) -> None:
        if not self.datasource_id:
            return
        self.client.get(
            f"/api/v1/datasources/{self.datasource_id}/reports",
            headers=self._headers(),
        )
