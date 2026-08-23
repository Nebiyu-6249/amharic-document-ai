"""PII redaction before egress (control C-41, threats T-07/T-20/T-26)."""

from __future__ import annotations

import pytest

from adai.security.redaction import redact


@pytest.mark.parametrize(
    ("text", "must_not_contain"),
    [
        ("write to almaz@school.edu.et please", "almaz@school.edu.et"),
        ("call 0911234567", "0911234567"),
        ("call +251911234567", "+251911234567"),
        ("national id 1234567890", "1234567890"),
        ("dated 12/03/2026", "12/03/2026"),
    ],
)
def test_deterministic_identifiers_are_removed(text: str, must_not_contain: str) -> None:
    assert must_not_contain not in redact(text).text


def test_grades_and_short_numbers_survive() -> None:
    """Redaction must not destroy the data the document exists to record."""
    result = redact("mathematics 87 out of 100, age 14")
    assert "87" in result.text
    assert "100" in result.text


def test_amharic_text_is_preserved() -> None:
    result = redact("ሰላም ለዓለም almaz@x.et")
    assert "ሰላም ለዓለም" in result.text
    assert "almaz@x.et" not in result.text


def test_counts_are_reported() -> None:
    result = redact("a@b.et and c@d.et")
    assert result.counts["email"] == 2
    assert result.redacted_anything


def test_is_complete_is_false_because_names_are_not_detected() -> None:
    """The honesty guard.

    Amharic personal names have no reliable surface pattern, so no regex can find them.
    is_complete must stay False until a trained NER model exists -- otherwise a caller
    could treat a transcription still containing a student's name as de-identified.
    """
    assert redact("ሰላም").is_complete is False
    assert redact("").is_complete is False


def test_clean_text_is_unchanged() -> None:
    result = redact("nothing sensitive here")
    assert result.text == "nothing sensitive here"
    assert not result.redacted_anything
