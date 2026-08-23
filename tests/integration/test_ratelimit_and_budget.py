"""Rate limiting (C-11, C-13, C-33) and AI budget (C-32) against a live Redis."""

from __future__ import annotations

import uuid

import pytest

from adai.ai.budget import check_and_consume_user_quota, check_global_spend, record_spend
from adai.security.csrf import issue_token, revoke_token, validate_token
from adai.security.ratelimit import (
    challenge_required,
    check_rate_limit,
    clear_auth_failures,
    compute_backoff_delay,
    get_failure_count,
    record_auth_failure,
)

pytestmark = [pytest.mark.integration, pytest.mark.security]


@pytest.fixture
def redis():
    from adai.redis_client import get_redis

    return get_redis()


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4()}"


# --- C-11 / C-33: fixed-window limits ------------------------------------------------


async def test_requests_are_allowed_up_to_the_limit_then_refused(redis) -> None:
    key = _unique("bucket")
    decisions = [
        await check_rate_limit(redis, "test", key, limit=3, window_seconds=60) for _ in range(5)
    ]
    assert [d.allowed for d in decisions] == [True, True, True, False, False]
    assert decisions[-1].retry_after_seconds > 0


async def test_limits_are_per_identifier(redis) -> None:
    a, b = _unique("a"), _unique("b")
    for _ in range(3):
        await check_rate_limit(redis, "test", a, limit=3, window_seconds=60)
    # a is exhausted; b must be unaffected.
    assert (await check_rate_limit(redis, "test", a, limit=3, window_seconds=60)).allowed is False
    assert (await check_rate_limit(redis, "test", b, limit=3, window_seconds=60)).allowed is True


async def test_inference_limit_is_tighter_than_the_general_one(redis) -> None:
    """C-33: the most expensive surface gets the strictest budget."""
    key = _unique("infer")
    general = [
        (await check_rate_limit(redis, "general", key, limit=60, window_seconds=60)).allowed
        for _ in range(5)
    ]
    inference = [
        (await check_rate_limit(redis, "inference", key, limit=2, window_seconds=60)).allowed
        for _ in range(5)
    ]
    assert all(general)
    assert inference.count(True) == 2


# --- C-13: progressive delay, both axes ---------------------------------------------


def test_backoff_grows_and_is_capped() -> None:
    delays = [compute_backoff_delay(n) for n in range(8)]
    assert delays[0] == 0.0
    assert delays == sorted(delays), "backoff must be monotonic"
    assert max(delays) <= 8.0, "an uncapped delay would itself be a DoS"


def test_challenge_is_demanded_only_after_repeated_failures() -> None:
    assert not challenge_required(0)
    assert not challenge_required(4)
    assert challenge_required(5)


async def test_failures_count_on_both_account_and_ip_axes(redis) -> None:
    """Per-account alone lets a botnet spread; per-IP alone lets one host walk a list."""
    account, ip_one, ip_two = _unique("acct"), _unique("ip1"), _unique("ip2")
    for _ in range(3):
        await record_auth_failure(redis, account, ip_one)
    # Same account from a fresh IP still carries the account's history.
    assert await get_failure_count(redis, account, ip_two) == 3
    # A fresh account from the used IP carries the IP's history.
    assert await get_failure_count(redis, _unique("acct"), ip_one) == 3


async def test_success_clears_the_counters(redis) -> None:
    account, ip = _unique("acct"), _unique("ip")
    await record_auth_failure(redis, account, ip)
    await record_auth_failure(redis, account, ip)
    assert await get_failure_count(redis, account, ip) == 2
    await clear_auth_failures(redis, account, ip)
    assert await get_failure_count(redis, account, ip) == 0


async def test_there_is_no_hard_lockout(redis) -> None:
    """C-13 / R-02: an account must never become permanently unusable, or anyone who
    knows an email address could deny it at will."""
    account, ip = _unique("acct"), _unique("ip")
    for _ in range(50):
        await record_auth_failure(redis, account, ip)
    # Still bounded, still recoverable.
    assert compute_backoff_delay(await get_failure_count(redis, account, ip)) <= 8.0
    await clear_auth_failures(redis, account, ip)
    assert await get_failure_count(redis, account, ip) == 0


# --- C-08: CSRF token storage --------------------------------------------------------


async def test_csrf_token_roundtrip_and_revocation(redis) -> None:
    session_id = _unique("sess")
    token = await issue_token(redis, session_id)
    assert await validate_token(redis, session_id, token)
    assert not await validate_token(redis, session_id, "wrong")
    assert not await validate_token(redis, session_id, None)
    assert not await validate_token(redis, _unique("other"), token)
    await revoke_token(redis, session_id)
    assert not await validate_token(redis, session_id, token)


# --- C-32: quotas and the fail-closed breaker ----------------------------------------


async def test_user_quota_is_consumed_and_then_refuses(redis) -> None:
    user = _unique("user")
    allowed = [
        (await check_and_consume_user_quota(redis, user, daily_quota=3)).allowed for _ in range(5)
    ]
    assert allowed == [True, True, True, False, False]


async def test_global_spend_breaker_trips_at_the_cap(redis) -> None:
    # The spend counter is global by design (that is what makes it a circuit breaker),
    # so it carries across tests. Reset it here rather than weakening the control.
    import datetime as dt

    await redis.delete(f"aispend:{dt.datetime.now(dt.UTC):%Y%m%d}:global")

    assert (await check_global_spend(redis, daily_cap_usd=1.0)).allowed is True
    await record_spend(redis, 1.5)
    decision = await check_global_spend(redis, daily_cap_usd=1.0)
    assert decision.allowed is False
    assert decision.code == "spend_cap"


async def test_breaker_fails_closed_when_redis_is_unreachable() -> None:
    """The decisive property: unable to read the meter means refuse, not proceed."""
    from redis.asyncio import Redis

    unreachable = Redis.from_url("redis://127.0.0.1:6399/0", socket_connect_timeout=1)
    try:
        decision = await check_global_spend(unreachable, daily_cap_usd=100.0)
        assert decision.allowed is False
        assert decision.code == "budget_backend_unavailable"

        quota = await check_and_consume_user_quota(unreachable, "u", daily_quota=100)
        assert quota.allowed is False
    finally:
        await unreachable.aclose()
