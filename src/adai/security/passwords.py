"""Password hashing (control C-06) and timing-equalised verification (C-12)."""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from argon2.low_level import Type

#: Argon2id. Parameters follow current OWASP guidance for a server-side hash:
#: 64 MiB memory, 3 iterations, 4 lanes. Tuned for ~100ms on target hardware -- retune
#: on the deployment host, not on a laptop.
_HASHER = PasswordHasher(
    time_cost=3, memory_cost=65536, parallelism=4, hash_len=32, salt_len=16, type=Type.ID
)

#: Verified against this on a nonexistent account so login costs the same either way.
#: Without it, "user not found" returns fast and "wrong password" returns slow, which
#: is a timing oracle for user enumeration (T-09).
_DUMMY_HASH = _HASHER.hash("dummy-password-for-timing-equalisation")


def hash_password(password: str) -> str:
    return _HASHER.hash(password)


def verify_password(password: str, encoded_hash: str | None) -> bool:
    """Verify a password, taking the same work whether or not the account exists.

    Pass ``None`` for ``encoded_hash`` when the account was not found: the dummy hash
    is verified instead, so the timing profile is indistinguishable (C-12).
    """
    target = encoded_hash if encoded_hash is not None else _DUMMY_HASH
    try:
        _HASHER.verify(target, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
    return encoded_hash is not None


def needs_rehash(encoded_hash: str) -> bool:
    return _HASHER.check_needs_rehash(encoded_hash)
