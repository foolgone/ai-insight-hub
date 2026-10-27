"""验收：验证 Sentry 错误上报链路（本地接收端代替 SaaS DSN）。

做法：
1. 起一个本地 HTTP 接收端，模拟 Sentry 的 envelope 接口；
2. 在该进程内设置 SENTRY_DSN 后导入 settings/sentry，确保初始化时读到 DSN；
3. init_sentry() → capture_exception(RuntimeError(...)) → flush；
4. 断言接收端收到 envelope 且包含异常类型/消息。

运行：backend 目录
    .\\venv\\Scripts\\python.exe scripts\\sentry_capture_check.py
"""
from __future__ import annotations

import http.server
import os
import socketserver
import sys
import threading
from pathlib import Path

# 允许 `python scripts/xxx.py` 方式运行（把 backend 根目录加入 sys.path）
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

CAPTURED: list[str] = []


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802 - http.server 约定
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length)
        if (self.headers.get("Content-Encoding") or "").lower() == "gzip":
            import gzip

            raw = gzip.decompress(raw)
        CAPTURED.append(raw.decode("utf-8", "replace"))
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, *_args: object) -> None:  # 静默
        return


def main() -> int:
    server = socketserver.TCPServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()

    # 必须在导入 app.core.config/sentry 之前设置，确保 settings 读到 DSN
    os.environ["SENTRY_DSN"] = f"http://publickey@127.0.0.1:{port}/1"
    os.environ["SENTRY_ENVIRONMENT"] = "acceptance-local"

    from app.core.config import settings  # noqa: PLC0415 - 顺序要求
    from app.core.sentry import capture_exception, init_sentry  # noqa: PLC0415

    print(f"SENTRY_DSN={settings.SENTRY_DSN}")
    print(f"SENTRY_ENVIRONMENT={settings.SENTRY_ENVIRONMENT}")
    if not init_sentry():
        print("[FAIL] init_sentry 返回 False")
        return 1

    capture_exception(
        RuntimeError("acceptance-sentry-check"),
        extra={"acceptance": True, "source": "sentry_capture_check"},
    )
    import sentry_sdk  # noqa: PLC0415

    sentry_sdk.flush(timeout=10)
    server.shutdown()

    payload = "\n".join(CAPTURED)
    ok = bool(CAPTURED) and "acceptance-sentry-check" in payload and "RuntimeError" in payload
    print(f"接收端收到请求数：{len(CAPTURED)}，总字节：{len(payload)}")
    print(f"包含异常消息：{'acceptance-sentry-check' in payload}")
    print(f"包含异常类型：{'RuntimeError' in payload}")
    print("[PASS] Sentry 上报链路可用" if ok else "[FAIL] 未捕获到 Sentry envelope")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
