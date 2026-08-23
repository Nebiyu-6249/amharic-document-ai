"""Unicode normalisation and homophone folding (ADR-0006).

Two distinct operations that must never be confused:

* :func:`to_nfc` runs on **ingest** and is safe to persist. It only fixes encoding
  form, never spelling.
* :func:`fold_homophones` is for **metrics only** and must never touch stored
  transcriptions. Folding rewrites what the writer actually wrote; the user's document
  says what it says, and orthographic choice is research signal.
"""

from __future__ import annotations

import unicodedata
from functools import lru_cache

from adai.ethiopic.inventory import HOMOPHONE_FAMILIES, VOWEL_ORDERS


@lru_cache(maxsize=1)
def _fold_table() -> dict[int, str]:
    """Build the codepoint -> canonical-character translation table.

    The Ethiopic core block is a strict 8-column grid (base at ``cp % 8 == 0``, vowel
    orders 1..7 at offsets 0..6), so a family declared by its order-1 bases expands
    across all seven orders arithmetically.
    """
    table: dict[int, str] = {}
    for bases in HOMOPHONE_FAMILIES.values():
        canonical, *rest = bases
        for order in range(VOWEL_ORDERS):
            target = chr(canonical + order)
            for other in rest:
                table[other + order] = target
    return table


def to_nfc(text: str) -> str:
    """Normalise to NFC. Safe to persist."""
    return unicodedata.normalize("NFC", text)


def fold_homophones(text: str) -> str:
    """Fold interchangeable Ethiopic glyphs to one canonical member per family.

    Metrics only. Folds 35 codepoints across four families. See ADR-0006 for why raw
    CER alone is misleading for this script -- two honest annotators disagree on these
    glyphs, and every disagreement scores as a substitution against a model that read
    the page correctly.
    """
    return text.translate(_fold_table())


def normalise_for_metrics(text: str) -> str:
    """The full metric-side normalisation: NFC, then homophone folding."""
    return fold_homophones(to_nfc(text))
