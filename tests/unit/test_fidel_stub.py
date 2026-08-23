"""The Fidel loader must refuse loudly rather than guess a schema (ADR-0008)."""

from __future__ import annotations

import pytest

from adai.data.fidel import FidelNotAvailableError, is_available, load_split


def test_load_split_raises_with_an_actionable_message() -> None:
    with pytest.raises(FidelNotAvailableError) as exc:
        load_split("train")
    message = str(exc.value)
    assert "not implemented" in message.lower()
    assert "huggingface.co" in message
    assert "allowlist" in message


def test_it_is_a_notimplementederror_so_callers_cannot_mistake_it_for_data() -> None:
    assert issubclass(FidelNotAvailableError, NotImplementedError)


def test_is_available_reports_false_when_absent() -> None:
    assert is_available() is False
