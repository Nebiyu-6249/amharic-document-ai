"""The Ethiopic codepoint inventory this project supports.

Figures are computed from the Unicode Character Database, not hard-coded from a web
page: unicode.org is not reachable from the build environment and the UCD is the
better source anyway. docs/research/verify_ethiopic_inventory.py re-derives every
number quoted in docs/RESEARCH.md section 5.

Measured against UCD 17.0.0: 523 assigned codepoints across five blocks, of which 481
are syllables. Note that Ethiopic Extended-B is **astral** (U+1E7E0+), so nothing in
this project may assume the Basic Multilingual Plane.
"""

from __future__ import annotations

from typing import Final

import unicodedata2 as ucd

#: (name, first, last) for every Ethiopic block, inclusive.
ETHIOPIC_BLOCKS: Final[tuple[tuple[str, int, int], ...]] = (
    ("Ethiopic", 0x1200, 0x137F),
    ("Ethiopic Supplement", 0x1380, 0x139F),
    ("Ethiopic Extended", 0x2D80, 0x2DDF),
    ("Ethiopic Extended-A", 0xAB00, 0xAB2F),
    ("Ethiopic Extended-B", 0x1E7E0, 0x1E7FF),
)

#: U+1361 ETHIOPIC WORDSPACE. The classical Ge'ez word separator. Modern Amharic uses
#: U+0020 instead, but HHD-Ethiopic ground truth is entirely wordspace-delimited, so a
#: WER definition that ignores this scores a near-perfect classical transcription at
#: roughly 100% error. See ADR-0006.
WORDSPACE: Final[str] = "፡"

#: U+1362 ETHIOPIC FULL STOP.
FULL_STOP: Final[str] = "።"

#: The nine Ethiopic punctuation marks, U+1360..U+1368.
PUNCTUATION: Final[frozenset[str]] = frozenset(chr(cp) for cp in range(0x1360, 0x1369))

#: Ge'ez numerals, U+1369..U+137C. Unicode category No, and **non-positional** --
#: int() will not parse them and a dedicated parser is required for ledgers.
GEEZ_NUMERALS: Final[frozenset[str]] = frozenset(chr(cp) for cp in range(0x1369, 0x137D))

#: Homophone equivalence classes: orthographically interchangeable in modern Amharic.
#: Each value is the order-1 base codepoint of a family member; the canonical target is
#: the first (lowest). The Ethiopic core block is a strict 8-column grid, so extending a
#: family across all seven vowel orders is just base+0..6 -- which is why this table is
#: four rows rather than thirty-five.
HOMOPHONE_FAMILIES: Final[dict[str, tuple[int, ...]]] = {
    "H": (0x1200, 0x1210, 0x1280),  # ha / hha / xa            -> /h/
    "S": (0x1220, 0x1230),  # sza / sa                 -> /s/
    "TS": (0x1338, 0x1340),  # tsa / tza                -> /ts'/
    "GLOTT": (0x12A0, 0x12D0),  # glottal a / pharyngeal a -> /?/
}

#: Number of vowel orders in the abugida grid.
VOWEL_ORDERS: Final[int] = 7


def ethiopic_codepoints() -> frozenset[int]:
    """Every assigned Ethiopic codepoint, computed from the UCD."""
    return frozenset(
        cp
        for _, lo, hi in ETHIOPIC_BLOCKS
        for cp in range(lo, hi + 1)
        if ucd.name(chr(cp), None) is not None
    )


def is_ethiopic(char: str) -> bool:
    """True if ``char`` is an assigned codepoint in any Ethiopic block."""
    if len(char) != 1:
        raise ValueError(f"expected a single character, got {len(char)}")
    cp = ord(char)
    return any(lo <= cp <= hi for _, lo, hi in ETHIOPIC_BLOCKS) and (
        ucd.name(char, None) is not None
    )
