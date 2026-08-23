"""Transport controls (C-01, C-02, C-03) and deferred payment controls (C-43, C-44)."""

from __future__ import annotations

import time
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from adai.payments.webhooks import (
    PRICE_CATALOGUE,
    REPLAY_TOLERANCE_SECONDS,
    WebhookRejectedError,
    compute_signature,
    resolve_price,
    verify_signature,
    verify_webhook,
)

pytestmark = pytest.mark.security


# --- C-01 / C-02: HTTPS enforcement and HSTS ---------------------------------------


def _app(*, force_https: bool):
    import os

    os.environ["ADAI_FORCE_HTTPS"] = "true" if force_https else "false"
    from adai.api.main import create_app
    from adai.config import get_settings

    get_settings.cache_clear()
    app = create_app()
    os.environ["ADAI_FORCE_HTTPS"] = "false"
    get_settings.cache_clear()
    return app


async def test_plain_http_is_redirected_when_https_is_forced() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=_app(force_https=True)), base_url="http://testserver"
    ) as client:
        response = await client.get("/healthz")
    assert response.status_code == 308
    assert response.headers["location"].startswith("https://")


async def test_hsts_is_sent_on_https_with_a_long_max_age() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=_app(force_https=True)), base_url="https://testserver"
    ) as client:
        response = await client.get("/healthz", headers={"x-forwarded-proto": "https"})
    hsts = response.headers["strict-transport-security"]
    assert "includeSubDomains" in hsts
    assert int(hsts.split("max-age=")[1].split(";")[0]) >= 31_536_000
    # Not preloaded: preload is effectively irreversible and the domain is not stable.
    assert "preload" not in hsts


async def test_no_hsts_on_plain_http() -> None:
    """Sending HSTS over http is meaningless and browsers ignore it."""
    async with AsyncClient(
        transport=ASGITransport(app=_app(force_https=False)), base_url="http://testserver"
    ) as client:
        response = await client.get("/healthz")
    assert "strict-transport-security" not in response.headers


async def test_server_implementation_is_not_advertised() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=_app(force_https=False)), base_url="http://testserver"
    ) as client:
        response = await client.get("/healthz")
    assert "server" not in {k.lower() for k in response.headers}


# --- C-43 / C-44: deferred payment controls ----------------------------------------


class _FakeRedis:
    """Minimal SET NX / EX stand-in for replay tests."""

    def __init__(self) -> None:
        self.store: dict[str, bytes] = {}

    async def set(self, key: str, value: bytes, ex: int | None = None, nx: bool = False):
        if nx and key in self.store:
            return None
        self.store[key] = value
        return True


def test_signature_covers_the_timestamp() -> None:
    """Otherwise an attacker keeps a valid signature and moves the clock."""
    body = b'{"event":"paid"}'
    assert compute_signature("s", 100, body) != compute_signature("s", 200, body)


def test_signature_verifies_and_rejects() -> None:
    body = b'{"event":"paid"}'
    good = compute_signature("secret", 1000, body)
    assert verify_signature("secret", 1000, body, good)
    assert not verify_signature("secret", 1000, body, "deadbeef")
    assert not verify_signature("other-secret", 1000, body, good)


async def test_valid_webhook_is_accepted_once_then_replay_is_refused() -> None:
    redis = _FakeRedis()
    body = b'{"event":"paid"}'
    now = int(time.time())
    signature = compute_signature("secret", now, body)
    kwargs = {
        "secret": "secret",
        "timestamp": now,
        "body": body,
        "signature": signature,
        "event_id": "evt_1",
        "now": now,
    }
    assert (await verify_webhook(redis, **kwargs)).event_id == "evt_1"  # type: ignore[arg-type]
    with pytest.raises(WebhookRejectedError) as exc:
        await verify_webhook(redis, **kwargs)  # type: ignore[arg-type]
    assert exc.value.code == "replay"


async def test_stale_but_correctly_signed_webhook_is_refused() -> None:
    redis = _FakeRedis()
    body = b"{}"
    old = int(time.time()) - REPLAY_TOLERANCE_SECONDS - 60
    with pytest.raises(WebhookRejectedError) as exc:
        await verify_webhook(
            redis,
            secret="s",
            timestamp=old,
            body=body,
            signature=compute_signature("s", old, body),
            event_id="evt_old",
            now=int(time.time()),
        )
    assert exc.value.code == "stale_timestamp"


async def test_bad_signature_is_refused_before_anything_else() -> None:
    redis = _FakeRedis()
    with pytest.raises(WebhookRejectedError) as exc:
        await verify_webhook(
            redis,
            secret="s",
            timestamp=int(time.time()),
            body=b"{}",
            signature="wrong",
            event_id="evt_x",
        )
    assert exc.value.code == "bad_signature"


def test_price_comes_from_the_server_not_the_client() -> None:
    """C-44: there is no code path that accepts a client-supplied amount."""
    assert resolve_price("credits_100") == Decimal("5.00")
    assert all(isinstance(v, Decimal) for v in PRICE_CATALOGUE.values())
    with pytest.raises(WebhookRejectedError):
        resolve_price("credits_free_lol")


def test_payments_are_disabled_by_default() -> None:
    from adai.config import Settings

    settings = Settings(secret_key="a" * 40, database_url="postgresql+psycopg://u:p@h/d")  # type: ignore[call-arg]
    assert settings.payments_enabled is False
