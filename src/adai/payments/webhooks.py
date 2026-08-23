"""Payment webhook verification and price authority.

**Deferred (threat T-25).** There is no payment provider in v1. These controls are
implemented and tested but gated behind ``ADAI_PAYMENTS_ENABLED``, which defaults to
false, and no route mounts them. They exist now so that turning payments on is a
configuration change rather than a security project, and so the controls cannot later
be mistaken for scope creep -- T-25 is in the threat model.

* **C-43** -- webhook signature verification plus replay protection. A signature alone
  is not enough: a valid signed webhook captured off the wire can be replayed to credit
  an account twice, so timestamp tolerance and single-use event ids are both required.
* **C-44** -- server-side price authority. The amount is looked up from a server-side
  catalogue, never taken from the client.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Final

from redis.asyncio import Redis

#: Reject webhooks whose timestamp is outside this window, even if correctly signed.
REPLAY_TOLERANCE_SECONDS: Final[int] = 300
_SEEN_PREFIX: Final[str] = "webhook:seen:"
#: Keep event ids at least as long as the tolerance window allows a replay.
_SEEN_TTL: Final[int] = REPLAY_TOLERANCE_SECONDS * 4

#: Server-side price catalogue (control C-44). The client never supplies an amount.
PRICE_CATALOGUE: Final[dict[str, Decimal]] = {
    "credits_100": Decimal("5.00"),
    "credits_500": Decimal("20.00"),
}


class WebhookRejectedError(Exception):
    def __init__(self, reason: str, code: str) -> None:
        super().__init__(reason)
        self.reason = reason
        self.code = code


@dataclass(frozen=True)
class VerifiedWebhook:
    event_id: str
    timestamp: int


def compute_signature(secret: str, timestamp: int, body: bytes) -> str:
    """HMAC-SHA256 over ``timestamp.body``.

    The timestamp is inside the signed material; otherwise an attacker could keep a
    valid signature and simply change the timestamp to defeat the replay window.
    """
    payload = f"{timestamp}.".encode() + body
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def verify_signature(secret: str, timestamp: int, body: bytes, presented: str) -> bool:
    return hmac.compare_digest(compute_signature(secret, timestamp, body), presented)


async def verify_webhook(
    redis: Redis,
    *,
    secret: str,
    timestamp: int,
    body: bytes,
    signature: str,
    event_id: str,
    now: int | None = None,
) -> VerifiedWebhook:
    """Full check: signature, freshness, then single-use (control C-43)."""
    now = now if now is not None else int(time.time())

    if not verify_signature(secret, timestamp, body, signature):
        raise WebhookRejectedError("signature mismatch", "bad_signature")

    if abs(now - timestamp) > REPLAY_TOLERANCE_SECONDS:
        raise WebhookRejectedError("timestamp outside tolerance", "stale_timestamp")

    # SET NX is atomic, so two concurrent deliveries cannot both win.
    first_time = await redis.set(f"{_SEEN_PREFIX}{event_id}", b"1", ex=_SEEN_TTL, nx=True)
    if not first_time:
        raise WebhookRejectedError("event already processed", "replay")

    return VerifiedWebhook(event_id=event_id, timestamp=timestamp)


def resolve_price(sku: str) -> Decimal:
    """Server-side price authority (control C-44). Never trust a client amount."""
    try:
        return PRICE_CATALOGUE[sku]
    except KeyError as exc:
        raise WebhookRejectedError(f"unknown sku: {sku}", "unknown_sku") from exc
