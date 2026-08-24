#!/usr/bin/env python3
"""Regenerate references/inventory.md from the Unicode Character Database.

The reference tables are generated rather than typed so they cannot drift from the
codebase. Run this after any Unicode upgrade or change to HOMOPHONE_FAMILIES:

    python .claude/skills/ethiopic-script/scripts/regenerate_inventory.py

Requires `unicodedata2` (the 3.11 stdlib only ships UCD 14) and the `adai` package on
the path.
"""

from __future__ import annotations

import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "src"))

import unicodedata2 as ucd  # noqa: E402

from adai.ethiopic.inventory import (  # noqa: E402
    ETHIOPIC_BLOCKS,
    HOMOPHONE_FAMILIES,
    VOWEL_ORDERS,
)

OUT = pathlib.Path(__file__).resolve().parents[1] / "references" / "inventory.md"


def main() -> int:
    lines: list[str] = []
    add = lines.append

    add("# Ethiopic inventory reference\n")
    add(f"Generated from the Unicode Character Database, UCD {ucd.unidata_version}, by")
    add("`.claude/skills/ethiopic-script/scripts/regenerate_inventory.py`.")
    add("Do not hand-edit: regenerate it.\n")
    add("## Contents\n")
    add("- [Per-block counts](#per-block-counts)")
    add("- [The 8-column grid](#the-8-column-grid)")
    add("- [Complete homophone fold table](#complete-homophone-fold-table)")
    add("- [Punctuation and numerals](#punctuation-and-numerals)\n")

    add("## Per-block counts\n")
    add("| Block | Range | Slots | Assigned | Categories |")
    add("|---|---|---|---|---|")
    total = 0
    for name, lo, hi in ETHIOPIC_BLOCKS:
        assigned = [cp for cp in range(lo, hi + 1) if ucd.name(chr(cp), None)]
        total += len(assigned)
        cats: dict[str, int] = {}
        for cp in assigned:
            category = ucd.category(chr(cp))
            cats[category] = cats.get(category, 0) + 1
        catstr = ", ".join(f"{k}:{v}" for k, v in sorted(cats.items()))
        add(f"| {name} | U+{lo:04X}–U+{hi:04X} | {hi - lo + 1} | **{len(assigned)}** | {catstr} |")
    add(f"| **TOTAL** | | | **{total}** | |\n")

    add("## The 8-column grid\n")
    add("The core block U+1200–U+1357 is laid out as a strict grid: the base consonant sits")
    add("at `cp % 8 == 0`, vowel orders 1–7 occupy offsets 0–6, and offset 7 holds a")
    add("labialised or extra form. Order *n* of a base is simply `base + n`.\n")
    add("This regularity is what makes factored decoding viable (ADR-0005): a 37-way base")
    add("head and a 7-way vowel head cover 259 syllables with 44 output classes, so a rare")
    add("syllable is rare only as a *pair* while its components stay common.\n")

    rows, complete, labialised = [], 0, 0
    for base in range(0x1200, 0x1358, 8):
        cells = [ucd.name(chr(base + off), None) for off in range(8)]
        if any(cells):
            rows.append((base, cells))
        if all(cells[i] for i in range(7)):
            complete += 1
        if cells[7]:
            labialised += 1
    add(f"- grid rows: **{len(rows)}**")
    add(f"- rows with a complete 7-vowel series: **{complete}**  ← the base-consonant inventory")
    add(f"- rows with the 8th (labialised) slot filled: **{labialised}**\n")
    add("First six complete series:\n")
    add("| Base | 1-ä | 2-u | 3-i | 4-a | 5-e | 6-ə | 7-o |")
    add("|---|---|---|---|---|---|---|")
    shown = 0
    for base, cells in rows:
        if not all(cells[i] for i in range(7)):
            continue
        add("| U+%04X | %s |" % (base, " | ".join(chr(base + i) for i in range(7))))
        shown += 1
        if shown == 6:
            break
    add("")

    add("## Complete homophone fold table\n")
    add("Metrics only. Never write these substitutions back to stored text.\n")
    add("| Family | Order | Members | Canonical |")
    add("|---|---|---|---|")
    folded = 0
    for family, bases in HOMOPHONE_FAMILIES.items():
        for order in range(VOWEL_ORDERS):
            members = [b + order for b in bases]
            cells_text = " · ".join(f"{chr(c)} U+{c:04X}" for c in members)
            add(f"| {family} | {order + 1} | {cells_text} | {chr(members[0])} |")
            folded += len(members) - 1
    add(f"\n**{folded} codepoints** are folded away in total.\n")

    add("## Punctuation and numerals\n")
    add("| Codepoint | Char | Category | Name |")
    add("|---|---|---|---|")
    for cp in range(0x1360, 0x137D):
        name = ucd.name(chr(cp), None)
        if name:
            add(
                f"| U+{cp:04X} | {chr(cp)} | {ucd.category(chr(cp))} | "
                f"{name[len('ETHIOPIC '):]} |"
            )
    add("")
    add("The `No` entries are **non-positional**: there is no place value, so `int()` will")
    add("not parse them and a dedicated Ge'ez numeral parser is required.")

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)} ({len(lines)} lines, UCD {ucd.unidata_version})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
