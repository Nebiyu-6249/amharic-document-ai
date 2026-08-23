"""Job queue access for the API process.

The API only ever *enqueues*; it never executes pipeline work. That is the ADR-0011
rule -- no HTTP request may block on inference -- and keeping the enqueue helper in its
own module means the API never imports anything from :mod:`adai.worker`, which is where
the ML dependencies would eventually live (ADR-0007).
"""

from __future__ import annotations

import asyncio

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from adai.config import get_settings
from adai.logging import get_logger

log = get_logger("adai.queue")

_pool: ArqRedis | None = None
_pool_loop: asyncio.AbstractEventLoop | None = None


async def get_pool() -> ArqRedis:
    """Return a connection pool bound to the running event loop.

    A redis connection pool holds loop-bound resources, so a pool cached on one loop
    raises when reused on another. Under uvicorn there is only ever one loop, but tests
    (and anything that calls asyncio.run more than once) create several -- so the loop
    is tracked and the pool rebuilt when it changes.
    """
    global _pool, _pool_loop
    loop = asyncio.get_running_loop()
    if _pool is None or _pool_loop is not loop:
        _pool = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
        _pool_loop = loop
    return _pool


async def enqueue_document(document_id: str) -> str | None:
    """Queue a document for processing. Returns the job id, or None if not queued.

    The job id is derived from the document id so a duplicate enqueue is deduplicated
    by arq rather than producing a second pipeline run.
    """
    pool = await get_pool()
    job = await pool.enqueue_job("process_document", document_id, _job_id=f"doc:{document_id}")
    return job.job_id if job is not None else None


async def close_pool() -> None:
    global _pool, _pool_loop
    if _pool is not None:
        await _pool.aclose()
    _pool = None
    _pool_loop = None
