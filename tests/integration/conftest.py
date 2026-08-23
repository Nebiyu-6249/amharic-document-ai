"""Integration fixtures. These need a live Postgres; they are marked accordingly."""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session", autouse=True)
def _migrated_database() -> None:
    """Apply migrations once per session against the configured test database."""
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")},
    )


@pytest_asyncio.fixture
async def client(tmp_path: Path) -> AsyncIterator[AsyncClient]:
    os.environ["ADAI_BLOB_ROOT"] = str(tmp_path / "blobs")
    from adai.config import get_settings

    get_settings.cache_clear()
    from adai.api.main import create_app

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        yield ac


@pytest_asyncio.fixture(autouse=True)
async def _reset_queue_pool() -> AsyncIterator[None]:
    """Each test runs on its own event loop; drop the cached pool with it."""
    yield
    from adai.queue import close_pool

    await close_pool()


@pytest_asyncio.fixture(autouse=True)
async def _clean_tables() -> AsyncIterator[None]:
    from sqlalchemy import text

    from adai.db import get_sessionmaker

    yield
    async with get_sessionmaker()() as session:
        await session.execute(text("TRUNCATE users, audit_events CASCADE"))
        await session.commit()
