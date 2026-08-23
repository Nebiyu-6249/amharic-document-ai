"""Ethiopic script handling: inventory, normalisation, tokenisation.

Single owner of every script-level decision in this project (ADR-0006). No other
module may reimplement homophone folding or word splitting -- inconsistency between
modules silently corrupts metrics.
"""

from adai.ethiopic.inventory import (
    ETHIOPIC_BLOCKS,
    HOMOPHONE_FAMILIES,
    PUNCTUATION,
    WORDSPACE,
    ethiopic_codepoints,
    is_ethiopic,
)
from adai.ethiopic.normalise import fold_homophones, normalise_for_metrics, to_nfc
from adai.ethiopic.tokenise import split_words

__all__ = [
    "ETHIOPIC_BLOCKS",
    "HOMOPHONE_FAMILIES",
    "PUNCTUATION",
    "WORDSPACE",
    "ethiopic_codepoints",
    "fold_homophones",
    "is_ethiopic",
    "normalise_for_metrics",
    "split_words",
    "to_nfc",
]
