"""Ethiopic inventory, normalisation and tokenisation (ADR-0006)."""

from __future__ import annotations

import pytest

from adai.ethiopic import (
    ethiopic_codepoints,
    fold_homophones,
    is_ethiopic,
    normalise_for_metrics,
    split_words,
)
from adai.ethiopic.inventory import GEEZ_NUMERALS, PUNCTUATION, WORDSPACE


def test_inventory_matches_documented_figure() -> None:
    # docs/RESEARCH.md section 5.1, computed against UCD 17.0.0.
    assert len(ethiopic_codepoints()) == 523


def test_extended_b_is_astral() -> None:
    """Ethiopic Extended-B lives above the BMP; nothing may assume 16-bit chars."""
    assert 0x1E7E0 in ethiopic_codepoints()
    assert max(ethiopic_codepoints()) > 0xFFFF


def test_is_ethiopic() -> None:
    assert is_ethiopic("ሀ")
    assert is_ethiopic("፡")
    assert not is_ethiopic("A")
    assert not is_ethiopic(" ")


def test_is_ethiopic_rejects_multichar() -> None:
    with pytest.raises(ValueError):
        is_ethiopic("ab")


@pytest.mark.parametrize(
    ("variants", "canonical"),
    [
        ("ሀሐኀ", "ሀ"),  # /h/ family, order 1
        ("ሃሓኃ", "ሃ"),  # /h/ family, order 4
        ("ሠሰ", "ሠ"),  # /s/ family
        ("ጸፀ", "ጸ"),  # /ts'/ family
        ("አዐ", "አ"),  # glottal/pharyngeal
    ],
)
def test_homophone_families_fold_to_one(variants: str, canonical: str) -> None:
    assert fold_homophones(variants) == canonical * len(variants)


def test_folding_covers_all_seven_orders() -> None:
    """The grid is regular, so every family folds across all 7 vowel orders."""
    for order in range(7):
        variants = "".join(chr(base + order) for base in (0x1200, 0x1210, 0x1280))
        assert len(set(fold_homophones(variants))) == 1


def test_folding_leaves_other_characters_alone() -> None:
    assert fold_homophones("ለም A1 ።") == "ለም A1 ።"


def test_split_words_classical_uses_wordspace() -> None:
    """HHD-Ethiopic ground truth is wordspace-delimited; whitespace-only splitting
    would score a perfect transcription at ~100% WER."""
    text = "ወጽራኅየኒ፡ቦአ፡ቅድሜሁ፡ውስተ፡ዕዘኒሁ"
    assert len(split_words(text)) == 5


def test_split_words_modern_uses_space() -> None:
    assert split_words("ሰላም ለዓለም") == ["ሰላም", "ለዓለም"]


def test_split_words_mixed_conventions() -> None:
    assert split_words("ሰላም፡ለዓለም ሁሉ") == ["ሰላም", "ለዓለም", "ሁሉ"]


def test_split_words_ignores_empty_tokens() -> None:
    assert split_words(f"  ሰላም{WORDSPACE}{WORDSPACE} ለዓለም  ") == ["ሰላም", "ለዓለም"]


def test_normalise_for_metrics_is_nfc_plus_fold() -> None:
    assert normalise_for_metrics("ሰላም") == fold_homophones("ሰላም")


def test_punctuation_and_numerals_present() -> None:
    assert WORDSPACE in PUNCTUATION
    assert len(PUNCTUATION) == 9
    assert len(GEEZ_NUMERALS) == 20
    # Ge'ez numerals are non-positional; int() must not be used on them.
    with pytest.raises(ValueError):
        int("፩")
