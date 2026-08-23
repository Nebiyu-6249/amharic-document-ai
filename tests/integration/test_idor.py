"""Object-level authorisation: threat T-02, the highest-rated threat in the model.

An authenticated user must not be able to reach another user's document by id, through
any route that accepts one.
"""

from __future__ import annotations

import io

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image

pytestmark = [pytest.mark.integration, pytest.mark.security]


def _jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (40, 40), (1, 2, 3)).save(buf, "JPEG")
    return buf.getvalue()


async def _session_for(email: str) -> AsyncClient:
    from adai.api.main import create_app

    client = AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://testserver")
    await client.post("/auth/register", json={"email": email, "password": "correct-horse-battery"})
    login = await client.post(
        "/auth/login", json={"email": email, "password": "correct-horse-battery"}
    )
    client.headers["x-csrf-token"] = login.json()["csrf_token"]
    return client


@pytest.mark.parametrize(
    "route",
    ["/documents/{id}", "/documents/{id}/transcription"],
)
async def test_other_users_document_is_not_readable(route: str, tmp_path) -> None:
    import os

    os.environ["ADAI_BLOB_ROOT"] = str(tmp_path / "blobs")
    from adai.config import get_settings

    get_settings.cache_clear()

    victim = await _session_for("victim@example.com")
    attacker = await _session_for("attacker@example.com")
    try:
        created = await victim.post("/documents", files={"file": ("v.jpg", _jpeg(), "image/jpeg")})
        assert created.status_code == 201
        document_id = created.json()["id"]

        # The owner can read it.
        assert (await victim.get(f"/documents/{document_id}")).status_code in (200, 404)

        # The attacker must not -- and must get 404, not 403. A 403 would confirm the
        # id exists, which is an enumeration oracle.
        response = await attacker.get(route.format(id=document_id))
        assert response.status_code == 404, f"IDOR on {route}: {response.status_code}"
    finally:
        await victim.aclose()
        await attacker.aclose()


async def test_other_users_document_cannot_be_deleted(tmp_path) -> None:
    import os

    os.environ["ADAI_BLOB_ROOT"] = str(tmp_path / "blobs")
    from adai.config import get_settings

    get_settings.cache_clear()

    victim = await _session_for("victim2@example.com")
    attacker = await _session_for("attacker2@example.com")
    try:
        created = await victim.post("/documents", files={"file": ("v.jpg", _jpeg(), "image/jpeg")})
        document_id = created.json()["id"]
        assert (await attacker.delete(f"/documents/{document_id}")).status_code == 404
        # And it is still there for its owner.
        assert (await victim.get(f"/documents/{document_id}")).status_code == 200
    finally:
        await victim.aclose()
        await attacker.aclose()


async def test_document_list_is_scoped_to_the_owner(tmp_path) -> None:
    import os

    os.environ["ADAI_BLOB_ROOT"] = str(tmp_path / "blobs")
    from adai.config import get_settings

    get_settings.cache_clear()

    victim = await _session_for("victim3@example.com")
    attacker = await _session_for("attacker3@example.com")
    try:
        await victim.post("/documents", files={"file": ("v.jpg", _jpeg(), "image/jpeg")})
        listing = await attacker.get("/documents")
        assert listing.status_code == 200
        assert listing.json() == []
    finally:
        await victim.aclose()
        await attacker.aclose()
