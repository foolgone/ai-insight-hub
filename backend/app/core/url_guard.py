"""用户可配置外部地址的安全校验（SSRF 防护）。

BYOK 里 LLM 的 ``base_url`` 一律拒绝；ASR 必须允许用户填自己的服务地址，
因此保存前在这里做一次校验：

- 只允许 ``https``（自建内网可用 ``ASR_ALLOW_HTTP=true`` 放开）；
- 禁止 URL 中携带账号密码；
- 域名解析后**任一** IP 落在内网/回环/链路本地/保留段即拒绝（防打内网）；
- 运维可用 ``ASR_ALLOWED_HOSTS`` 白名单跳过 IP 检查（自建内网 ASR）。

DNS 重绑定无法在纯 HTTP 客户端层彻底消除，MVP 在保存时校验一次，
并约定该地址由用户自己填写、仅用于调用其 ASR 服务。
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit

from app.core.config import settings

__all__ = ["UnsafeUrlError", "assert_safe_base_url", "allowed_hosts"]

# ipaddress 未覆盖、但同样不该被访问的网段
_EXTRA_BLOCKED = tuple(
    ipaddress.ip_network(item)
    for item in (
        "100.64.0.0/10",  # 运营商级 NAT
        "192.0.0.0/24",  # IETF 协议分配
        "198.18.0.0/15",  # 基准测试
    )
)


class UnsafeUrlError(ValueError):
    """地址不满足安全要求。"""


def allowed_hosts() -> set[str]:
    return {
        item.strip().lower()
        for item in (settings.ASR_ALLOWED_HOSTS or "").split(",")
        if item.strip()
    }


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None:
        return _is_blocked_ip(mapped)
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        return True
    return any(ip.version == net.version and ip in net for net in _EXTRA_BLOCKED)


def _assert_host_safe(host: str) -> None:
    """字面 IP 直接判定；域名解析后逐个校验。"""
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None

    if literal is not None:
        if _is_blocked_ip(literal):
            raise UnsafeUrlError("不允许使用内网/回环地址")
        return

    try:
        infos = socket.getaddrinfo(host, None)
    except OSError as exc:
        raise UnsafeUrlError(f"域名无法解析：{host}") from exc

    for info in infos:
        address = info[4][0]
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:  # pragma: no cover - getaddrinfo 只回 IP
            continue
        if _is_blocked_ip(ip):
            raise UnsafeUrlError("域名解析到内网/回环地址，已拒绝")


def assert_safe_base_url(url: str) -> str:
    """校验并返回规范化（去尾斜杠）的 base_url；不安全抛 ``UnsafeUrlError``。"""
    raw = (url or "").strip()
    if not raw:
        raise UnsafeUrlError("服务地址不能为空")

    parts = urlsplit(raw)
    if parts.scheme not in {"http", "https"}:
        raise UnsafeUrlError("服务地址必须以 http:// 或 https:// 开头")
    if parts.scheme == "http" and not settings.ASR_ALLOW_HTTP:
        raise UnsafeUrlError("服务地址必须使用 https")
    if parts.username or parts.password:
        raise UnsafeUrlError("服务地址不能包含账号密码")
    if not parts.hostname:
        raise UnsafeUrlError("服务地址缺少主机名")
    if parts.query or parts.fragment:
        raise UnsafeUrlError("服务地址不能包含查询参数或锚点")

    host = parts.hostname.lower()
    if host not in allowed_hosts():
        _assert_host_safe(host)

    path = parts.path.rstrip("/")
    return f"{parts.scheme}://{parts.netloc}{path}"
