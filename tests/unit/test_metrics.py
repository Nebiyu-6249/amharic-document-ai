"""Evaluation metrics."""

from __future__ import annotations

import pytest

from adai.eval.metrics import (
    EvalReport,
    character_error_rate,
    field_f1,
    kendall_tau,
    layout_map,
    normalisation_aware_cer,
    normalised_edit_distance,
    wer,
)


def test_identical_strings_are_zero_error() -> None:
    assert character_error_rate("ሰላም", "ሰላም") == 0.0
    assert wer("ሰላም ለዓለም", "ሰላም ለዓለም") == 0.0


def test_homophone_difference_inflates_raw_cer_but_not_normalised() -> None:
    """The core ADR-0006 claim, as an assertion rather than a paragraph."""
    reference, hypothesis = "ሰላም ለዓለም", "ሠላም ለዓለም"
    assert character_error_rate(reference, hypothesis) > 0
    assert normalisation_aware_cer(reference, hypothesis) == 0.0


def test_empty_reference_with_output_is_total_error() -> None:
    assert character_error_rate("", "abc") == 1.0
    assert character_error_rate("", "") == 0.0


def test_ned_is_bounded() -> None:
    assert 0.0 <= normalised_edit_distance("abc", "xyz") <= 1.0
    assert normalised_edit_distance("", "") == 0.0


def test_wer_counts_words_not_characters() -> None:
    assert wer("ሰላም ለዓለም", "ሰላም ዓለም") == pytest.approx(0.5)


def test_wer_on_classical_text_is_not_catastrophic() -> None:
    """Regression guard: splitting on whitespace alone would make this ~1.0."""
    reference = "ወጽራኅየኒ፡ቦአ፡ቅድሜሁ"
    hypothesis = "ወጽራኅየኒ፡ቦአ፡ቅድሜህ"
    assert wer(reference, hypothesis) == pytest.approx(1 / 3)


def test_kendall_tau_extremes() -> None:
    assert kendall_tau([0, 1, 2, 3], [0, 1, 2, 3]) == 1.0
    assert kendall_tau([0, 1, 2, 3], [3, 2, 1, 0]) == -1.0


def test_kendall_tau_detects_column_transposition() -> None:
    """Perfect characters, wrong order: accuracy would not catch this, tau does."""
    assert kendall_tau([0, 1, 2, 3], [2, 3, 0, 1]) < 1.0


def test_kendall_tau_rejects_mismatched_lengths() -> None:
    with pytest.raises(ValueError):
        kendall_tau([0, 1], [0])


def test_field_f1_uses_metric_normalisation() -> None:
    _, _, f1 = field_f1({"name": "ሰላም"}, {"name": "ሠላም"})
    assert f1 == 1.0


def test_field_f1_penalises_wrong_value() -> None:
    _, _, f1 = field_f1({"grade": "80"}, {"grade": "90"})
    assert f1 == 0.0


def test_layout_map_perfect_and_missed() -> None:
    assert layout_map([("para", (0, 0, 10, 10))], [("para", (0, 0, 10, 10), 0.9)])["mAP"] == 1.0
    assert layout_map([("para", (0, 0, 10, 10))], [("para", (50, 50, 60, 60), 0.9)])["mAP"] == 0.0


def test_eval_report_always_carries_both_cer_figures() -> None:
    """Structural enforcement of the 'report both' rule."""
    report = EvalReport(
        split="iid",
        corpus="fidel",
        n_samples=1,
        cer=0.1,
        normalisation_aware_cer=0.05,
        wer=0.2,
        ned=0.1,
    )
    payload = report.as_dict()
    assert "cer" in payload and "normalisation_aware_cer" in payload
