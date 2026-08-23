"""Rate limiting and progressive authentication delay.

Implements:

* **C-11** -- password-reset limits, per account AND per IP.
* **C-13** -- progressive delay plus a challenge, rather than a hard account lockout.
* **C-33** -- a separate, tighter limit for the inference endpoint, which is the most
  expensive surface we expose (threat T-06).

On C-13, from THREAT_MODEL.md section 6.2: a hard lock after N failures turns an
authentication control into a denial-of-service weapon, because anyone who knows an
email address can lock that account at will, for free. The accepted cost is weaker
resistance to a patient distributed attacker (residual risk R-02).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from redis.asyncio import Redis

_RATE_PREFIX: Final[str] = "rl:"
_FAIL_PREFIX: Final[str] = "authfail:"

#: Failures before a challenge is demanded. Delay begins before this.
CHALLENGE_AFTER_FAILURES: Final[int] = 5
#: Cap on the computed delay. Long enough to throttle, short enough not to be a DoS.
MAX_DELAY_SECONDS: Final[float] = 8.0
#: Failure counters decay, so a legitimate user is never permanently penalised.
FAILURE_WINDOW_SECONDS: Final[int] = 900


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    remaining: int
    retry_after_seconds: int


async def check_rate_limit(
    redis: Redis, bucket: str, identifier: str, *, limit: int, window_seconds: int
) -> RateLimitDecision:
    """Fixed-window counter.

    Chosen over a sliding log because it is one INCR plus one EXPIRE, so it cannot
    itself become a resource-exhaustion vector under the flood it is meant to stop.
    """
    key = f"{_RATE_PREFIX}{bucket}:{identifier}"
    count = int(await redis.incr(key))
    if count == 1:
        await redis.expire(key, window_seconds)
    ttl = int(await redis.ttl(key))
    retry_after = ttl if ttl and ttl > 0 else window_seconds
    return RateLimitDecision(
        allowed=count <= limit,
        remaining=max(0, limit - count),
        retry_after_seconds=int(retry_after),
    )


def compute_backoff_delay(failure_count: int) -> float:
    """Exponential backoff for authentication failures (C-13).

    0 failures -> no delay. Then 0.25s, 0.5s, 1s, 2s ... capped. The point is to make
    automated guessing expensive without ever making the account unusable.
    """
    if failure_count <= 0:
        return 0.0
    return min(MAX_DELAY_SECONDS, 0.25 * (2.0 ** (failure_count - 1)))


async def record_auth_failure(redis: Redis, account_key: str, ip_key: str) -> int:
    """Record a failure against both axes and return the higher count.

    Both axes matter: per-account alone lets a botnet spread across IPs, per-IP alone
    lets one host walk a list of accounts.
    """
    counts = []
    for scope, value in (("acct", account_key), ("ip", ip_key)):
        key = f"{_FAIL_PREFIX}{scope}:{value}"
        count = int(await redis.incr(key))
        if count == 1:
            await redis.expire(key, FAILURE_WINDOW_SECONDS)
        counts.append(count)
    return max(counts)


async def get_failure_count(redis: Redis, account_key: str, ip_key: str) -> int:
    counts = []
    for scope, value in (("acct", account_key), ("ip", ip_key)):
        raw = await redis.get(f"{_FAIL_PREFIX}{scope}:{value}")
        counts.append(int(raw) if raw else 0)
    return max(counts)


async def clear_auth_failures(redis: Redis, account_key: str, ip_key: str) -> None:
    """Called on successful authentication."""
    await redis.delete(f"{_FAIL_PREFIX}acct:{account_key}", f"{_FAIL_PREFIX}ip:{ip_key}")


def challenge_required(failure_count: int) -> bool:
    """Whether a bot challenge should be demanded before another attempt (C-13/C-14)."""
    return failure_count >= CHALLENGE_AFTER_FAILURES
