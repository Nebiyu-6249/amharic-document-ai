"""Controls C-06 (Argon2id) and C-12 (no timing oracle on account existence)."""

from __future__ import annotations

import statistics
import time

from adai.security.passwords import hash_password, verify_password


def test_hash_is_argon2id_not_a_fast_hash() -> None:
    encoded = hash_password("correct horse battery staple")
    assert encoded.startswith("$argon2id$")


def test_hashes_are_salted() -> None:
    assert hash_password("same") != hash_password("same")


def test_verify_roundtrip() -> None:
    encoded = hash_password("s3cret-passphrase")
    assert verify_password("s3cret-passphrase", encoded)
    assert not verify_password("wrong", encoded)


def test_missing_account_still_verifies_against_a_dummy_hash() -> None:
    """Passing None must return False without short-circuiting the work."""
    assert not verify_password("anything", None)


def test_missing_account_still_does_real_argon2_work() -> None:
    """C-12 / T-09: a fast "user not found" path is an enumeration oracle.

    The defect this guards against is a *short circuit* -- returning before hashing --
    which is an order-of-magnitude difference (microseconds vs tens of milliseconds),
    not a few percent. So the assertion is an absolute floor plus a generous ratio
    band. Tight ratio bounds would only buy flakiness: Argon2id allocates 64 MiB per
    call and this runs on shared CPU.
    """
    encoded = hash_password("a-real-password")

    def median_seconds(hash_value: str | None, runs: int = 5) -> float:
        samples = []
        for _ in range(runs):
            start = time.perf_counter()
            verify_password("guess", hash_value)
            samples.append(time.perf_counter() - start)
        return statistics.median(samples)

    existing = median_seconds(encoded)
    missing = median_seconds(None)

    # The decisive assertion: the missing-account path spent real hashing time.
    assert missing > 0.005, (
        f"missing-account path returned in {missing * 1000:.2f}ms - short circuit?"
    )
    # And it is the same order of magnitude as a genuine verification.
    assert 0.25 < missing / existing < 4.0, (
        f"timing profiles diverge: missing={missing * 1000:.1f}ms existing={existing * 1000:.1f}ms"
    )
