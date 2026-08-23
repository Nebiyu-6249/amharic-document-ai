"""Shared Redis client for CSRF tokens, rate limits and AI budget counters."""

from __future__ import annotations

import asyncio

from redis.asyncio import Redis

from adai.config import get_settings

_client: Redis | None = None
_client_loop: asyncio.AbstractEventLoop | None = None


def get_redis() -> Redis:
    """Return a Redis client bound to the running event loop.

    A redis client holds loop-bound connection resources, so one cached on a different
    loop raises "attached to a different loop" at the first command. Under uvicorn there
    is only ever one loop; anything that creates more (tests, repeated asyncio.run) gets
    a fresh client.
    """
    global _client, _client_loop
    try:
        loop: asyncio.AbstractEventLoop | None = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if _client is None or _client_loop is not loop:
        _client = Redis.from_url(get_settings().redis_url, decode_responses=False)
        _client_loop = loop
    return _client


async def close_redis() -> None:
    global _client, _client_loop
    if _client is not None:
        await _client.aclose()
    _client = None
    _client_loop = None
