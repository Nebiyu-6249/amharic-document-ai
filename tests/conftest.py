"""Shared fixtures."""

from __future__ import annotations

import io
import os

import pytest

os.environ.setdefault("ADAI_SECRET_KEY", "test-only-secret-key-at-least-32-chars-long")
os.environ.setdefault(
    "ADAI_DATABASE_URL", "postgresql+psycopg://adai_app:devpassword@127.0.0.1:5432/adai"
)
os.environ.setdefault("ADAI_ENVIRONMENT", "test")
os.environ.setdefault("ADAI_FORCE_HTTPS", "false")


@pytest.fixture
def jpeg_bytes() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (64, 48), (200, 30, 30)).save(buf, "JPEG")
    return buf.getvalue()


@pytest.fixture
def png_bytes() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (32, 32), (10, 20, 30)).save(buf, "PNG")
    return buf.getvalue()
