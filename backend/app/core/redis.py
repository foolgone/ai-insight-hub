"""Redis 客户端与 Token 黑名单（API 设计 §2.4）。

- 登出/刷新轮换：把 token 的 ``jti`` 写入黑名单，TTL = token 剩余有效期；
- 认证依赖命中黑名单即返回 401（``AUTH_TOKEN_EXPIRED``）。
"""
from __future__ import annotations

from redis.asyncio import Redis

from app.core.config import settings

BLACKLIST_PREFIX = "auth:blacklist:"

_redis: Redis | None = None


def get_redis() -> Redis:
    """懒加载 Redis 客户端（连接串来自 settings.REDIS_URL）。"""
    global _redis
    if _redis is None:
        _redis = Redis.from_url(
            settings.REDIS_URL,
            max_connections=settings.REDIS_MAX_CONNECTIONS,
            decode_responses=True,
        )
    return _redis


async def close_redis() -> None:
    """关闭客户端（应用退出/测试用例间调用，避免跨事件循环复用连接）。"""
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


async def blacklist_token(jti: str, ttl_seconds: int) -> None:
    """把 token 加入黑名单（TTL 到 token 过期即可自动清理）。"""
    if ttl_seconds <= 0:
        return
    await get_redis().setex(f"{BLACKLIST_PREFIX}{jti}", ttl_seconds, "1")


async def is_token_blacklisted(jti: str) -> bool:
    return bool(await get_redis().exists(f"{BLACKLIST_PREFIX}{jti}"))


async def clear_blacklist(jti: str) -> None:
    """测试辅助：清理单个黑名单键。"""
    await get_redis().delete(f"{BLACKLIST_PREFIX}{jti}")


__all__ = [
    "BLACKLIST_PREFIX",
    "blacklist_token",
    "clear_blacklist",
    "close_redis",
    "get_redis",
    "is_token_blacklisted",
]
