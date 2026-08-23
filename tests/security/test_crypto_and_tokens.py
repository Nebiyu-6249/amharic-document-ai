"""Field encryption (C-37) and password-reset tokens (C-10)."""

from __future__ import annotations

import datetime as dt

import pytest

from adai.security.crypto import (
    DecryptionError,
    decrypt_field,
    derive_key,
    encrypt_field,
    is_encrypted,
)
from adai.security.tokens import (
    TOKEN_TTL,
    expiry_from,
    generate_reset_token,
    hash_reset_token,
    is_expired,
    tokens_match,
)

KEY = derive_key("a" * 40)
SENSITIVE = "Student Almaz T., mathematics, 87/100"


# --- C-37 -------------------------------------------------------------------------


def test_roundtrip() -> None:
    assert decrypt_field(encrypt_field(SENSITIVE, KEY), KEY) == SENSITIVE


def test_ciphertext_does_not_contain_plaintext() -> None:
    assert "Almaz" not in encrypt_field(SENSITIVE, KEY)


def test_nonce_is_fresh_each_call() -> None:
    """GCM nonce reuse under one key is catastrophic; identical inputs must differ."""
    assert encrypt_field(SENSITIVE, KEY) != encrypt_field(SENSITIVE, KEY)


def test_tampered_ciphertext_is_rejected_not_silently_wrong() -> None:
    ciphertext = encrypt_field(SENSITIVE, KEY)
    with pytest.raises(DecryptionError):
        decrypt_field(ciphertext[:-6] + "AAAAAA", KEY)


def test_wrong_key_is_rejected() -> None:
    with pytest.raises(DecryptionError):
        decrypt_field(encrypt_field(SENSITIVE, KEY), derive_key("b" * 40))


def test_keys_are_domain_separated() -> None:
    """HKDF info/salt separation: the field key is not the signing key."""
    assert derive_key("same-secret", salt=b"s1") != derive_key("same-secret", salt=b"s2")


def test_version_prefix_present_for_rotation() -> None:
    assert is_encrypted(encrypt_field("x", KEY))


def test_unversioned_input_is_rejected() -> None:
    with pytest.raises(DecryptionError):
        decrypt_field("just-some-text", KEY)


# --- C-10 -------------------------------------------------------------------------


def test_token_plaintext_is_not_recoverable_from_the_stored_hash() -> None:
    plaintext, hashed = generate_reset_token()
    assert plaintext not in hashed
    assert len(hashed) == 64


def test_tokens_are_unpredictable() -> None:
    assert len({generate_reset_token()[0] for _ in range(50)}) == 50


def test_token_match_and_mismatch() -> None:
    plaintext, hashed = generate_reset_token()
    assert tokens_match(plaintext, hashed)
    assert not tokens_match(plaintext + "x", hashed)


def test_hash_is_deterministic() -> None:
    plaintext, hashed = generate_reset_token()
    assert hash_reset_token(plaintext) == hashed


def test_expiry_is_short() -> None:
    assert TOKEN_TTL <= dt.timedelta(hours=1)
    now = dt.datetime.now(dt.UTC)
    assert not is_expired(expiry_from(now), now)
    assert is_expired(expiry_from(now), now + TOKEN_TTL + dt.timedelta(seconds=1))
