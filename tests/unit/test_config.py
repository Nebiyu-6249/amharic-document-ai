"""Settings validation (controls C-04, C-35)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from adai.config import Settings

BASE = {
    "secret_key": "a" * 40,
    "database_url": "postgresql+psycopg://u:p@localhost/db",
}


def test_wildcard_cors_origin_is_refused() -> None:
    with pytest.raises(ValidationError, match="wildcard"):
        Settings(**BASE, cors_allow_origins=("*",))  # type: ignore[arg-type]


def test_short_secret_key_is_refused() -> None:
    with pytest.raises(ValidationError, match="at least 32"):
        Settings(secret_key="tooshort", database_url=BASE["database_url"])  # type: ignore[arg-type]


def test_llm_postcorrection_is_off_by_default() -> None:
    """ADR-0009: an LM must not silently rewrite a grade."""
    assert Settings(**BASE).llm_postcorrection_enabled is False  # type: ignore[arg-type]


def test_retention_default_is_ninety_days() -> None:
    assert Settings(**BASE).original_retention_days == 90  # type: ignore[arg-type]


def test_explicit_origin_allowlist_is_accepted() -> None:
    settings = Settings(**BASE, cors_allow_origins=("https://app.example.com",))  # type: ignore[arg-type]
    assert settings.cors_allow_origins == ("https://app.example.com",)


def test_auth_database_url_is_required_outside_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without it, RLS makes every login fail with a message that looks like a password
    problem. Startup must refuse rather than serve a broken login."""
    # Settings reads the ambient environment, which the test runner populates.
    monkeypatch.delenv("ADAI_AUTH_DATABASE_URL", raising=False)
    with pytest.raises(ValidationError, match="ADAI_AUTH_DATABASE_URL"):
        Settings(**BASE, environment="prod")  # type: ignore[arg-type]


def test_auth_database_url_may_be_omitted_in_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ADAI_AUTH_DATABASE_URL", raising=False)
    assert Settings(**BASE, environment="dev").auth_database_url is None  # type: ignore[arg-type]
