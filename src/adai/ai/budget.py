"""AI spend and quota enforcement (control C-32, threat T-06).

Three independent ceilings, because they fail differently:

* **per-request token cap** -- bounds one pathological document;
* **per-user daily job quota** -- bounds one abusive account;
* **global daily spend circuit breaker** -- bounds everything, including a bug in our
  own code, and is the only one that protects the budget when an attacker has many
  accounts.

The breaker **fails closed**. If Redis is unreachable we cannot know the current spend,
so we refuse. That is a deliberate availability-for-cost trade: the failure mode of
failing open is an unbounded bill, which ends the project (threat T-06); the failure
mode of failing closed is that post-correction is unavailable, and it is off by default
anyway (ADR-0009).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Final

from redis.asyncio import Redis
from redis.exceptions import RedisError

from adai.logging import get_logger

log = get_logger("adai.ai.budget")

_SPEND_PREFIX: Final[str] = "aispend:"
_QUOTA_PREFIX: Final[str] = "aiquota:"
#: Counters live slightly over a day so a UTC-day rollover cannot lose the tail.
_DAY_TTL: Final[int] = 60 * 60 * 26


class BudgetExceededError(Exception):
    """A ceiling was hit. Carries a machine-readable reason, never internal figures."""

    def __init__(self, reason: str, code: str) -> None:
        super().__init__(reason)
        self.reason = reason
        self.code = code


@dataclass(frozen=True)
class BudgetDecision:
    allowed: bool
    code: str = "ok"
    reason: str = ""


def _day_key(prefix: str, suffix: str, now: dt.datetime) -> str:
    return f"{prefix}{now.strftime('%Y%m%d')}:{suffix}"


def check_token_ceiling(requested_tokens: int, *, max_tokens: int) -> BudgetDecision:
    """Bound a single request (C-32)."""
    if requested_tokens > max_tokens:
        return BudgetDecision(
            allowed=False,
            code="token_ceiling",
            reason=f"request exceeds the {max_tokens}-token per-request ceiling",
        )
    return BudgetDecision(allowed=True)


async def check_and_consume_user_quota(
    redis: Redis, user_id: str, *, daily_quota: int, now: dt.datetime | None = None
) -> BudgetDecision:
    """Consume one unit of a user's daily job quota. Fails closed on Redis errors."""
    now = now or dt.datetime.now(dt.UTC)
    key = _day_key(_QUOTA_PREFIX, user_id, now)
    try:
        used = await redis.incr(key)
        if used == 1:
            await redis.expire(key, _DAY_TTL)
    except RedisError:
        log.error("budget_backend_unavailable", control="C-32", check="user_quota")
        return BudgetDecision(
            allowed=False, code="budget_backend_unavailable", reason="quota unavailable"
        )
    if used > daily_quota:
        return BudgetDecision(allowed=False, code="user_quota", reason="daily job quota exhausted")
    return BudgetDecision(allowed=True)


async def check_global_spend(
    redis: Redis, *, daily_cap_usd: float, now: dt.datetime | None = None
) -> BudgetDecision:
    """Global daily spend circuit breaker. **Fails closed.**"""
    now = now or dt.datetime.now(dt.UTC)
    key = _day_key(_SPEND_PREFIX, "global", now)
    try:
        raw = await redis.get(key)
    except RedisError:
        # Cannot read the meter, so we cannot know we are under the cap.
        log.error("budget_backend_unavailable", control="C-32", check="global_spend")
        return BudgetDecision(
            allowed=False,
            code="budget_backend_unavailable",
            reason="spend breaker unavailable; failing closed",
        )
    spent = float(raw) if raw else 0.0
    if spent >= daily_cap_usd:
        log.warning("spend_breaker_tripped", control="C-32")
        return BudgetDecision(allowed=False, code="spend_cap", reason="daily AI spend cap reached")
    return BudgetDecision(allowed=True)


async def record_spend(redis: Redis, amount_usd: float, *, now: dt.datetime | None = None) -> float:
    """Add to today's spend and return the new total. Never raises to the caller."""
    now = now or dt.datetime.now(dt.UTC)
    key = _day_key(_SPEND_PREFIX, "global", now)
    try:
        total = await redis.incrbyfloat(key, amount_usd)
        await redis.expire(key, _DAY_TTL)
        return float(total)
    except RedisError:
        # Losing a spend record must not crash a job, but it must be visible.
        log.error("spend_record_failed", control="C-32")
        return -1.0
