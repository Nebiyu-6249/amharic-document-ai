"""arq worker: runs the pipeline off the request path.

Jobs must be idempotent. arq gives at-least-once delivery, so a job that runs twice
must not produce two transcriptions or double-charge a quota.
"""

from __future__ import annotations

import datetime as dt
import uuid
from pathlib import Path
from typing import Any, ClassVar

from arq.connections import RedisSettings
from sqlalchemy import select

from adai.config import get_settings
from adai.db import get_worker_sessionmaker
from adai.logging import configure_logging, get_logger
from adai.models import Document, DocumentStatus, Transcription
from adai.pipeline.runner import run_pipeline
from adai.pipeline.types import PageInput

log = get_logger("adai.worker")


async def process_document(ctx: dict[str, Any], document_id: str) -> dict[str, Any]:
    """Run the pipeline for one document. Idempotent."""
    settings = get_settings()
    doc_uuid = uuid.UUID(document_id)

    async with get_worker_sessionmaker()() as session:
        document = await session.get(Document, doc_uuid)
        if document is None or document.deleted_at is not None:
            log.info("job_skipped", document_id=document_id, reason="missing_or_deleted")
            return {"status": "skipped"}

        # Idempotency: a completed document is not reprocessed on redelivery.
        existing = (
            await session.execute(
                select(Transcription).where(Transcription.document_id == doc_uuid).limit(1)
            )
        ).scalar_one_or_none()
        if existing is not None:
            log.info("job_skipped", document_id=document_id, reason="already_transcribed")
            return {"status": "already_done"}

        document.status = DocumentStatus.PROCESSING
        await session.commit()

    blob = Path(settings.blob_root) / document.blob_key
    try:
        image_bytes = blob.read_bytes()
        result = run_pipeline(
            PageInput(blob_key=document.blob_key, width=document.width, height=document.height),
            image_bytes,
        )
    except Exception:
        async with get_worker_sessionmaker()() as session:
            failed = await session.get(Document, doc_uuid)
            if failed is not None:
                failed.status = DocumentStatus.FAILED
                await session.commit()
        log.error("job_failed", document_id=document_id)
        raise

    async with get_worker_sessionmaker()() as session:
        session.add(
            Transcription(
                document_id=doc_uuid,
                schema_version=result.schema_version,
                structured={
                    "regions": result.regions,
                    "stages": [s.model_dump() for s in result.stages],
                },
                markdown=result.markdown,
                # C-41 has not run yet; redaction is a Phase 5 deliverable and this
                # flag must be true before anything crosses TB-06 to OpenAI.
                pii_redacted=False,
                pipeline_mode=settings.pipeline_mode,
                contains_stub_stages=result.contains_stub_stages,
            )
        )
        done = await session.get(Document, doc_uuid)
        if done is not None:
            done.status = DocumentStatus.COMPLETE
        await session.commit()

    log.info("job_complete", document_id=document_id, stub=result.contains_stub_stages)
    return {"status": "complete", "contains_stub_stages": result.contains_stub_stages}


async def purge_expired_originals(ctx: dict[str, Any]) -> dict[str, int]:
    """Retention sweep (control C-42, Q-5): delete original blobs past 90 days.

    Derived transcriptions are kept -- they are the research artefact and, once C-41
    redaction is implemented, they carry no personal data.
    """
    settings = get_settings()
    now = dt.datetime.now(dt.UTC)
    purged = 0
    async with get_worker_sessionmaker()() as session:
        stmt = select(Document).where(
            Document.originals_expire_at < now, Document.deleted_at.is_(None)
        )
        for document in (await session.execute(stmt)).scalars():
            (Path(settings.blob_root) / document.blob_key).unlink(missing_ok=True)
            document.deleted_at = now
            document.status = DocumentStatus.DELETED
            purged += 1
        await session.commit()
    log.info("retention_sweep", purged=purged)
    return {"purged": purged}


class WorkerSettings:
    """arq entrypoint: ``arq adai.worker.main.WorkerSettings``."""

    functions: ClassVar[list[Any]] = [process_document]
    cron_jobs: ClassVar[list[Any]] = []
    max_jobs = 4
    job_timeout = 600
    # arq reads this as a plain attribute, so it must be a RedisSettings instance
    # rather than a callable.
    redis_settings: ClassVar[RedisSettings] = RedisSettings.from_dsn(get_settings().redis_url)


configure_logging(json_output=True)
