"""Worker path: pipeline result persistence, stub honesty, deletion, idempotency."""

from __future__ import annotations

import datetime as dt
import io
import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient
from PIL import Image

pytestmark = pytest.mark.integration


def _jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (120, 90), (230, 228, 215)).save(buf, "JPEG")
    return buf.getvalue()


async def _authed(client: AsyncClient, email: str) -> None:
    await client.post("/auth/register", json={"email": email, "password": "correct-horse-battery"})
    await client.post("/auth/login", json={"email": email, "password": "correct-horse-battery"})


async def _run_pipeline_for(document_id: str) -> None:
    """Invoke the worker function directly, bypassing Redis."""
    from adai.worker.main import process_document

    await process_document({}, document_id)


async def test_transcription_endpoint_serialises_stored_stages(client: AsyncClient) -> None:
    """Regression: stored stages carry duration_ms, which StageOut forbids.

    The response schema deliberately omits internal timings (control C-21), so the
    handler must project onto declared fields rather than splatting the stored dict.
    Splatting raised ValidationError and produced a 500.
    """
    await _authed(client, "worker1@example.com")
    created = await client.post("/documents", files={"file": ("a.jpg", _jpeg(), "image/jpeg")})
    document_id = created.json()["id"]

    await _run_pipeline_for(document_id)

    response = await client.get(f"/documents/{document_id}/transcription")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["contains_stub_stages"] is True
    assert {s["stage"] for s in body["stages"]} == {
        "rectify",
        "layout",
        "lines",
        "recognise",
        "assemble",
    }
    # Internal timings must not leak into the response.
    assert all("duration_ms" not in s for s in body["stages"])


async def test_stub_output_is_empty_not_fabricated(client: AsyncClient) -> None:
    await _authed(client, "worker2@example.com")
    created = await client.post("/documents", files={"file": ("a.jpg", _jpeg(), "image/jpeg")})
    document_id = created.json()["id"]
    await _run_pipeline_for(document_id)

    body = (await client.get(f"/documents/{document_id}/transcription")).json()
    assert body["markdown"] == ""
    assert all(region["text"] == "" for region in body["regions"])
    # Every stub stage explains itself.
    for stage in body["stages"]:
        if stage["stub"]:
            assert stage["stub_reason"]


async def test_processing_is_idempotent(client: AsyncClient) -> None:
    """arq gives at-least-once delivery; a redelivered job must not duplicate work."""
    await _authed(client, "worker3@example.com")
    created = await client.post("/documents", files={"file": ("a.jpg", _jpeg(), "image/jpeg")})
    document_id = created.json()["id"]

    await _run_pipeline_for(document_id)
    await _run_pipeline_for(document_id)

    from sqlalchemy import func, select

    from adai.db import get_sessionmaker
    from adai.models import Transcription

    async with get_sessionmaker()() as session:
        count = await session.scalar(
            select(func.count())
            .select_from(Transcription)
            .where(Transcription.document_id == uuid.UUID(document_id))
        )
    assert count == 1


async def test_deletion_purges_the_blob(client: AsyncClient) -> None:
    """Control C-42 / Q-5: deletion must remove the file, not just the row."""
    from adai.config import get_settings

    await _authed(client, "worker4@example.com")
    created = await client.post("/documents", files={"file": ("a.jpg", _jpeg(), "image/jpeg")})
    document_id = created.json()["id"]

    from sqlalchemy import select

    from adai.db import get_sessionmaker
    from adai.models import Document

    async with get_sessionmaker()() as session:
        blob_key = await session.scalar(
            select(Document.blob_key).where(Document.id == uuid.UUID(document_id))
        )
    blob = Path(get_settings().blob_root) / str(blob_key)
    assert blob.is_file(), "upload did not persist a blob"

    assert (await client.delete(f"/documents/{document_id}")).status_code == 204
    assert not blob.exists(), "blob survived deletion"
    assert (await client.get(f"/documents/{document_id}")).status_code == 404


async def test_retention_deadline_is_set_on_every_upload(client: AsyncClient) -> None:
    """Q-5: originals expire after 90 days, and the column is NOT NULL."""
    await _authed(client, "worker5@example.com")
    created = await client.post("/documents", files={"file": ("a.jpg", _jpeg(), "image/jpeg")})
    body = created.json()
    uploaded = dt.datetime.fromisoformat(body["uploaded_at"])
    expires = dt.datetime.fromisoformat(body["originals_expire_at"])
    assert 89 <= (expires - uploaded).days <= 90
