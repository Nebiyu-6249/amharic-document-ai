"""End-to-end API behaviour against a real Postgres."""

from __future__ import annotations

import io

import pytest
from httpx import AsyncClient
from PIL import Image

pytestmark = pytest.mark.integration


def _jpeg(size: tuple[int, int] = (80, 60)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, (120, 90, 60)).save(buf, "JPEG")
    return buf.getvalue()


async def _register_and_login(client: AsyncClient, email: str) -> None:
    r = await client.post(
        "/auth/register", json={"email": email, "password": "correct-horse-battery"}
    )
    assert r.status_code == 202
    r = await client.post("/auth/login", json={"email": email, "password": "correct-horse-battery"})
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    # Every state-changing request now needs the CSRF synchroniser token (C-08).
    client.headers["x-csrf-token"] = r.json()["csrf_token"]


async def test_healthz_needs_no_database(client: AsyncClient) -> None:
    r = await client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


async def test_readyz_reaches_the_database(client: AsyncClient) -> None:
    r = await client.get("/readyz")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"


async def test_security_headers_present_on_every_response(client: AsyncClient) -> None:
    r = await client.get("/healthz")
    csp = r.headers["content-security-policy"]
    assert "unsafe-inline" not in csp
    assert "nonce-" in csp
    assert "frame-ancestors 'none'" in csp
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "geolocation=()" in r.headers["permissions-policy"]


async def test_upload_requires_authentication(client: AsyncClient) -> None:
    r = await client.post("/documents", files={"file": ("a.jpg", _jpeg(), "image/jpeg")})
    assert r.status_code == 401


async def test_full_upload_flow(client: AsyncClient) -> None:
    await _register_and_login(client, "alice@example.com")
    r = await client.post(
        "/documents",
        files={"file": ("scan.jpg", _jpeg(), "image/jpeg")},
        data={"research_opt_in": "false", "subject_is_minor": "true"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "pending"
    assert body["width"] == 80
    # C-21: internal fields must not be in the response.
    assert "blob_key" not in body
    assert "sha256" not in body
    assert "owner_id" not in body


async def test_upload_rejects_svg(client: AsyncClient) -> None:
    await _register_and_login(client, "svg@example.com")
    r = await client.post(
        "/documents",
        files={"file": ("x.svg", b"<svg><script>alert(1)</script></svg>", "image/svg+xml")},
    )
    assert r.status_code == 422


async def test_registration_does_not_reveal_existing_accounts(client: AsyncClient) -> None:
    """Control C-12 / threat T-09: identical status and body either way."""
    payload = {"email": "dup@example.com", "password": "correct-horse-battery"}
    first = await client.post("/auth/register", json=payload)
    second = await client.post("/auth/register", json=payload)
    assert first.status_code == second.status_code == 202
    assert first.json() == second.json()


async def test_login_failure_is_identical_for_unknown_and_wrong_password(
    client: AsyncClient,
) -> None:
    await _register_and_login(client, "known@example.com")
    unknown = await client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": "whatever-long-enough"}
    )
    wrong = await client.post(
        "/auth/login", json={"email": "known@example.com", "password": "wrong-password-here"}
    )
    assert unknown.status_code == wrong.status_code
    assert unknown.json() == wrong.json()


async def test_mass_assignment_is_rejected(client: AsyncClient) -> None:
    """Control C-20 / threat T-14."""
    r = await client.post(
        "/auth/register",
        json={"email": "mass@example.com", "password": "correct-horse-battery", "is_active": True},
    )
    assert r.status_code == 422
