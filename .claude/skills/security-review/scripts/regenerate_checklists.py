#!/usr/bin/env python3
"""Regenerate references/checklists.md from docs/SECURITY.md.

The checklist is derived rather than duplicated so it cannot drift from the real control
register. Run it after any change to the register:

    python .claude/skills/security-review/scripts/regenerate_checklists.py
"""

from __future__ import annotations

import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[4]
SECURITY = REPO / "docs" / "SECURITY.md"
OUT = pathlib.Path(__file__).resolve().parents[1] / "references" / "checklists.md"

#: Rows look like: | **C-01** | Control | T-11, T-23 | where | test | Status |
ROW = re.compile(
    r"^\|\s*\*\*(C-\d{2})\*\*\s*\|\s*(.+?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|$"
)
SECTION = re.compile(r"^### 2\.\d+\s+(.*)$")


def main() -> int:
    if not SECURITY.is_file():
        print(f"FAIL: {SECURITY} not found", file=sys.stderr)
        return 2

    lines = ["# Control checklists\n"]
    lines.append("Generated from `docs/SECURITY.md` by")
    lines.append("`.claude/skills/security-review/scripts/regenerate_checklists.py`.")
    lines.append("Do not hand-edit: regenerate it.\n")
    lines.append("Status vocabulary is used strictly. **Partial** means something real is")
    lines.append("implemented but the control is not fully discharged, and the gap is stated in")
    lines.append("docs/SECURITY.md §4. Treat Partial as an open item, not a pass.\n")

    current: str | None = None
    count = 0
    partial: list[str] = []
    for raw in SECURITY.read_text(encoding="utf-8").splitlines():
        if match := SECTION.match(raw):
            current = match.group(1)
            lines.append(f"\n## {current}\n")
            lines.append("| ID | Control | Threats | Implementation | Test | Status |")
            lines.append("|---|---|---|---|---|---|")
            continue
        if current and (match := ROW.match(raw)):
            cid, control, threats, where, test, status = match.groups()
            lines.append(f"| {cid} | {control} | {threats} | {where} | {test} | {status} |")
            count += 1
            if "Partial" in status:
                partial.append(f"{cid} ({current})")

    lines.append(f"\n---\n\n**{count} controls** in the register.\n")
    if partial:
        lines.append("Currently **Partial**, with the gap described in docs/SECURITY.md §4:\n")
        for item in partial:
            lines.append(f"- {item}")
        lines.append("")

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)}: {count} controls, {len(partial)} partial")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
