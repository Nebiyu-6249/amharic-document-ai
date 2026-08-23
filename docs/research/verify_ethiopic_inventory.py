#!/usr/bin/env python3
"""Regenerate every Unicode claim in docs/RESEARCH.md section 5.

These numbers are *computed*, not quoted from a web page, because unicode.org is
not reachable from the build environment and the Unicode Character Database is a
better source anyway.

Usage:
    pip install unicodedata2      # UCD 17.0.0; the 3.11 stdlib only ships UCD 14
    python docs/research/verify_ethiopic_inventory.py

Exits non-zero if any figure quoted in RESEARCH.md no longer holds.
"""

from __future__ import annotations

import sys

try:
    import unicodedata2 as ucd
except ImportError:  # pragma: no cover - fall back with a loud warning
    import unicodedata as ucd

    print(
        f"WARNING: unicodedata2 not installed; using stdlib UCD {ucd.unidata_version}. "
        "Figures in RESEARCH.md were computed against UCD 17.0.0.",
        file=sys.stderr,
    )

BLOCKS = [
    ("Ethiopic", 0x1200, 0x137F),
    ("Ethiopic Supplement", 0x1380, 0x139F),
    ("Ethiopic Extended", 0x2D80, 0x2DDF),
    ("Ethiopic Extended-A", 0xAB00, 0xAB2F),
    ("Ethiopic Extended-B", 0x1E7E0, 0x1E7FF),
]

# Homophone equivalence classes: orthographically interchangeable in modern
# Amharic. Keyed by family; values are the order-1 base codepoints. The canonical
# target is the first (lowest) member. See ADR-0006.
HOMOPHONE_FAMILIES = {
    "H": [0x1200, 0x1210, 0x1280],      # ha / hha / xa            -> /h/
    "S": [0x1220, 0x1230],              # sza / sa                 -> /s/
    "TS": [0x1338, 0x1340],             # tsa / tza                -> /ts'/
    "GLOTT": [0x12A0, 0x12D0],          # glottal a / pharyngeal a -> /?/
}

# Figures asserted in docs/RESEARCH.md section 5, against UCD 17.0.0.
EXPECTED = {
    "total_assigned": 523,
    "syllables": 481,
    "complete_series": 37,
    "labialised_slots": 34,
    "homophone_folded": 35,
}


def assigned(lo: int, hi: int) -> list[int]:
    return [cp for cp in range(lo, hi + 1) if ucd.name(chr(cp), None)]


def main() -> int:
    print(f"UCD version: {ucd.unidata_version}\n")

    total = 0
    print(f"{'BLOCK':<22}{'RANGE':<24}{'SLOTS':>6}{'ASSIGNED':>10}")
    for name, lo, hi in BLOCKS:
        found = assigned(lo, hi)
        total += len(found)
        rng = f"U+{lo:04X}..U+{hi:04X}"
        print(f"{name:<22}{rng:<24}{hi - lo + 1:>6}{len(found):>10}")
    print(f"{'TOTAL':<22}{'':<24}{'':>6}{total:>10}\n")

    syllables = sum(
        1
        for _, lo, hi in BLOCKS
        for cp in range(lo, hi + 1)
        if (n := ucd.name(chr(cp), None)) and n.startswith("ETHIOPIC SYLLABLE ")
    )

    # The core block is a strict 8-column grid: base at cp % 8 == 0,
    # vowel orders 1..7 at offsets 0..6, offset 7 a labialised/extra slot.
    complete_series = 0
    labialised_slots = 0
    for base in range(0x1200, 0x1358, 8):
        cells = [ucd.name(chr(base + off), None) for off in range(8)]
        if all(cells[i] for i in range(7)):
            complete_series += 1
        if cells[7]:
            labialised_slots += 1

    folded = sum(len(members) - 1 for members in HOMOPHONE_FAMILIES.values()) * 7

    results = {
        "total_assigned": total,
        "syllables": syllables,
        "complete_series": complete_series,
        "labialised_slots": labialised_slots,
        "homophone_folded": folded,
    }

    print(f"{'FIGURE':<22}{'COMPUTED':>10}{'EXPECTED':>10}  STATUS")
    failed = False
    for key, expected in EXPECTED.items():
        got = results[key]
        ok = got == expected
        failed |= not ok
        print(f"{key:<22}{got:>10}{expected:>10}  {'ok' if ok else 'MISMATCH'}")

    if failed:
        print(
            "\nFAIL: a figure quoted in docs/RESEARCH.md no longer holds. "
            "Either the UCD version changed or the document is stale.",
            file=sys.stderr,
        )
        return 1

    print("\nAll figures in docs/RESEARCH.md section 5 verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
