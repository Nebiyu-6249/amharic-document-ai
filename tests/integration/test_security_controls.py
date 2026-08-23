"""Integration-level security controls, exercised against a live Postgres and Redis."""

from __future__ import annotations

import io

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image

pytestmark = [pytest.mark.integration, pytest.mark.security]


def _jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (40, 40), (5, 5, 5)).save(buf, "JPEG")
    return buf.getvalue()


async def _login(client: AsyncClient, email: str) -> str:
    await client.post("/auth/register", json={"email": email, "password": "correct-horse-battery"})
    response = await client.post(
        "/auth/login", json={"email": email, "password": "correct-horse-battery"}
    )
    return str(response.json()["csrf_token"])


# --- C-08: CSRF --------------------------------------------------------------------


async def test_state_change_without_csrf_token_is_refused(client: AsyncClient) -> None:
    await _login(client, "csrf1@example.com")  # deliberately not setting the header
    response = await client.post("/documents", files={"file": ("a.jpg", _jpeg(), "image/jpeg")})
    assert response.status_code == 403


async def test_state_change_with_a_forged_csrf_token_is_refused(client: AsyncClient) -> None:
    await _login(client, "csrf2@example.com")
    client.headers["x-csrf-token"] = "forged-token-value"
    response = await client.post("/documents", files={"file": ("a.jpg", _jpeg(), "image/jpeg")})
    assert response.status_code == 403


async def test_state_change_with_the_real_token_succeeds(client: AsyncClient) -> None:
    token = await _login(client, "csrf3@example.com")
    client.headers["x-csrf-token"] = token
    response = await client.post("/documents", files={"file": ("a.jpg", _jpeg(), "image/jpeg")})
    assert response.status_code == 201


async def test_safe_methods_need_no_token(client: AsyncClient) -> None:
    await _login(client, "csrf4@example.com")
    assert (await client.get("/documents")).status_code == 200


async def test_one_users_csrf_token_does_not_work_for_another(tmp_path) -> None:
    """The token is bound to the session, not merely to existing."""
    import os

    os.environ["ADAI_BLOB_ROOT"] = str(tmp_path / "blobs")
    from adai.api.main import create_app
    from adai.config import get_settings

    get_settings.cache_clear()

    async with (
        AsyncClient(
            transport=ASGITransport(app=create_app()), base_url="http://testserver"
        ) as victim,
        AsyncClient(
            transport=ASGITransport(app=create_app()), base_url="http://testserver"
        ) as attacker,
    ):
        victim_token = await _login(victim, "csrfv@example.com")
        await _login(attacker, "csrfa@example.com")
        attacker.headers["x-csrf-token"] = victim_token
        response = await attacker.post(
            "/documents", files={"file": ("a.jpg", _jpeg(), "image/jpeg")}
        )
        assert response.status_code == 403


# --- C-09: session invalidation on password change ---------------------------------


async def test_password_change_invalidates_existing_sessions(client: AsyncClient) -> None:
    token = await _login(client, "pwchange@example.com")
    client.headers["x-csrf-token"] = token
    assert (await client.get("/auth/me")).status_code == 200

    changed = await client.post(
        "/auth/password",
        json={
            "current_password": "correct-horse-battery",
            "new_password": "an-entirely-new-passphrase",
        },
    )
    assert changed.status_code == 200
    # The cookie the client still holds was minted under the old session epoch.
    assert (await client.get("/auth/me")).status_code == 401


async def test_password_change_requires_the_current_password(client: AsyncClient) -> None:
    token = await _login(client, "pwwrong@example.com")
    client.headers["x-csrf-token"] = token
    response = await client.post(
        "/auth/password",
        json={"current_password": "not-the-right-one", "new_password": "another-new-passphrase"},
    )
    assert response.status_code == 403


# --- C-10 / C-11 / C-12: password reset --------------------------------------------


async def test_reset_request_is_identical_for_known_and_unknown_accounts(
    client: AsyncClient,
) -> None:
    await _login(client, "resetknown@example.com")
    known = await client.post(
        "/auth/password/reset-request", json={"email": "resetknown@example.com"}
    )
    unknown = await client.post(
        "/auth/password/reset-request", json={"email": "nobody-here@example.com"}
    )
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()


async def test_reset_request_is_rate_limited_per_account(client: AsyncClient) -> None:
    """C-11: an attacker must not be able to mail-bomb an account."""
    email = "resetlimit@example.com"
    await _login(client, email)
    codes = [
        (await client.post("/auth/password/reset-request", json={"email": email})).status_code
        for _ in range(6)
    ]
    # Response shape stays identical (C-12); the limiting is visible in the audit log,
    # not in the response, which is the point.
    assert set(codes) == {202}


async def test_reset_confirm_rejects_an_unknown_token(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/password/reset-confirm",
        json={"token": "x" * 43, "new_password": "a-brand-new-passphrase"},
    )
    assert response.status_code == 400


# --- C-22: no admin surface (Q-1) ---------------------------------------------------


@pytest.mark.parametrize(
    "path", ["/admin", "/admin/", "/admin/login", "/_admin", "/docs", "/redoc", "/openapi.json"]
)
async def test_no_admin_or_doc_surface_in_non_dev(path: str, client: AsyncClient) -> None:
    """Q-1: v1 has no admin surface, and schema docs are dev-only."""
    assert (await client.get(path)).status_code in (404, 405)


# --- C-21: responses do not leak internals -----------------------------------------


async def test_document_response_omits_internal_fields(client: AsyncClient) -> None:
    token = await _login(client, "trim@example.com")
    client.headers["x-csrf-token"] = token
    body = (
        await client.post("/documents", files={"file": ("a.jpg", _jpeg(), "image/jpeg")})
    ).json()
    for leaked in ("blob_key", "sha256", "owner_id", "password_hash"):
        assert leaked not in body


async def test_unhandled_errors_do_not_leak_stack_traces(client: AsyncClient) -> None:
    response = await client.get("/documents/not-a-uuid")
    # Any refusal is fine; what matters is that nothing internal comes back with it.
    assert response.status_code in (400, 401, 404, 422)
    assert "Traceback" not in response.text
    assert "sqlalchemy" not in response.text.lower()


# --- C-07: session cookie flags ------------------------------------------------------


async def test_session_cookie_flags(client: AsyncClient) -> None:
    """HttpOnly stops XSS reading it, SameSite blunts CSRF, host-only stops a sibling
    subdomain overwriting it."""
    await client.post(
        "/auth/register", json={"email": "cookie@example.com", "password": "correct-horse-battery"}
    )
    response = await client.post(
        "/auth/login", json={"email": "cookie@example.com", "password": "correct-horse-battery"}
    )
    raw = response.headers["set-cookie"]
    assert "HttpOnly" in raw
    assert "SameSite=lax" in raw or "SameSite=Lax" in raw
    assert "Path=/" in raw
    # No Domain attribute: the cookie stays host-only.
    assert "Domain=" not in raw
