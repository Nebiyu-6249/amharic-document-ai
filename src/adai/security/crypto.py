"""Authenticated encryption for sensitive columns at rest (control C-37, threats T-07/T-24).

AES-256-GCM via a key derived from ``ADAI_SECRET_KEY``. GCM rather than CBC because it
authenticates as well as encrypts: a tampered ciphertext fails to decrypt rather than
producing attacker-chosen plaintext.

**What this does and does not protect.** It defends against an attacker who obtains the
database contents alone -- a stolen backup, a misdirected dump, a curious operator with
read access to the tables but not the application host (T-24). It does NOT protect
against an attacker who has the application's key material, because the running
application must be able to read these values.

Ciphertexts are versioned so the scheme can be rotated without a flag day.
"""

from __future__ import annotations

import base64
import os
from typing import Final

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

#: Prefix marks the scheme so a future rotation can decrypt both forms.
_VERSION: Final[str] = "v1"
_NONCE_BYTES: Final[int] = 12
_KEY_BYTES: Final[int] = 32
_INFO: Final[bytes] = b"adai-field-encryption-v1"


class DecryptionError(Exception):
    """Ciphertext was corrupt, tampered with, or encrypted under another key."""


def derive_key(secret: str, *, salt: bytes = b"adai-field-salt") -> bytes:
    """Derive a 256-bit field-encryption key from the application secret.

    HKDF gives domain separation: the session-signing key and the field-encryption key
    are different keys, so compromise of one signature does not imply the other.
    """
    return HKDF(algorithm=hashes.SHA256(), length=_KEY_BYTES, salt=salt, info=_INFO).derive(
        secret.encode("utf-8")
    )


def encrypt_field(plaintext: str, key: bytes) -> str:
    """Encrypt to ``v1:<base64(nonce||ciphertext)>``.

    A fresh random nonce per call: GCM nonce reuse under the same key is catastrophic.
    """
    nonce = os.urandom(_NONCE_BYTES)
    blob = nonce + AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), None)
    return f"{_VERSION}:{base64.urlsafe_b64encode(blob).decode('ascii')}"


def decrypt_field(ciphertext: str, key: bytes) -> str:
    """Decrypt a value produced by :func:`encrypt_field`."""
    try:
        version, _, payload = ciphertext.partition(":")
        if version != _VERSION or not payload:
            raise DecryptionError(f"unsupported ciphertext version: {version!r}")
        blob = base64.urlsafe_b64decode(payload.encode("ascii"))
        nonce, body = blob[:_NONCE_BYTES], blob[_NONCE_BYTES:]
        return AESGCM(key).decrypt(nonce, body, None).decode("utf-8")
    except DecryptionError:
        raise
    except Exception as exc:
        raise DecryptionError("field could not be decrypted") from exc


def is_encrypted(value: str) -> bool:
    return value.startswith(f"{_VERSION}:")
