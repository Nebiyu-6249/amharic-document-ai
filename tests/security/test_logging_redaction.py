"""Control C-38: security events are logged, secrets and document text never are.

These tests capture real emitted output through an injected stream. An earlier version
used ``redirect_stderr``, which structlog bypasses because it caches the stderr handle
-- every "secret is absent" assertion passed against an empty string. Tests that pass
when the control is deleted are worse than no tests, so the seam exists deliberately.
"""

from __future__ import annotations

import io

import pytest

from adai.logging import configure_logging, get_logger


def _emit(**fields: object) -> str:
    stream = io.StringIO()
    configure_logging(json_output=True, stream=stream)
    get_logger("test").info("event", **fields)
    return stream.getvalue()


def test_capture_seam_actually_captures() -> None:
    """Guard the guard: if this fails, every assertion below is vacuous."""
    assert "hello" in _emit(harmless="hello")


def test_password_and_token_keys_are_redacted() -> None:
    out = _emit(password="hunter2", token="tok_abc123", session_id="sess_xyz")
    assert "[redacted]" in out
    assert "hunter2" not in out
    assert "tok_abc123" not in out
    assert "sess_xyz" not in out


def test_document_content_is_never_logged() -> None:
    """Transcription text is personal data (threat T-19)."""
    out = _emit(markdown="ሰላም ለዓለም", text="student name and grade")
    assert "ሰላም" not in out
    assert "student name" not in out


@pytest.mark.parametrize(
    "secret",
    [
        "sk-ABCDEFGHIJKLMNOPQRSTUVWX",
        "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ012345",
        "AKIAIOSFODNN7EXAMPLE",
    ],
)
def test_secret_shaped_values_caught_under_unexpected_keys(secret: str) -> None:
    assert secret not in _emit(note=f"value is {secret} here")


def test_database_dsn_credentials_are_redacted() -> None:
    assert "u:p@h" not in _emit(note="dsn postgresql://u:p@h/db")


def test_non_sensitive_fields_survive() -> None:
    """Redaction must not make the audit log useless."""
    out = _emit(event_type="login", outcome="failure")
    assert "login" in out
    assert "failure" in out
