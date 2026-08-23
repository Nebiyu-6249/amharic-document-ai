"""Password-reset tokens (control C-10, threat T-10).

Four properties, all of which matter:

* **cryptographically random** -- 32 bytes from ``secrets``, never a UUID or a counter;
* **hashed at rest** -- the database stores SHA-256 of the token, so a database read
  does not yield usable reset links. This is why SHA-256 and not Argon2: the token is
  high-entropy random, so there is nothing to brute-force, and reset verification must
  stay fast. Argon2 is for *low*-entropy human passwords;
* **short expiry** -- 30 minutes;
* **single use** -- consumed atomically, so a leaked link (referrer header, shared
  inbox, browser history) cannot be replayed.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import secrets
from typing import Final

#: Reset links are for immediate use.
TOKEN_TTL = dt.timedelta(minutes=30)
_TOKEN_BYTES: Final[int] = 32


def generate_reset_token() -> tuple[str, str]:
    """Return ``(plaintext, hashed)``.

    The plaintext goes in the email and is never persisted. The hash is what the
    database stores.
    """
    plaintext = secrets.token_urlsafe(_TOKEN_BYTES)
    return plaintext, hash_reset_token(plaintext)


def hash_reset_token(plaintext: str) -> str:
    """SHA-256 hex digest. See the module docstring for why not Argon2."""
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def tokens_match(presented_plaintext: str, stored_hash: str) -> bool:
    """Constant-time comparison of the hashed forms."""
    return hmac.compare_digest(hash_reset_token(presented_plaintext), stored_hash)


def expiry_from(now: dt.datetime) -> dt.datetime:
    return now + TOKEN_TTL


def is_expired(expires_at: dt.datetime, now: dt.datetime) -> bool:
    return now >= expires_at
