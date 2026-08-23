#!/usr/bin/env python3
"""Enforce the threat-model invariant from docs/THREAT_MODEL.md.

    "A control with no threat is scope creep; a threat with no control is a bug."

Parses the threat tables (section 5) and the control register (section 8) out of
THREAT_MODEL.md and checks three things:

  1. every threat cites at least one control;
  2. every control cites at least one threat;
  3. the two directions agree -- if a threat cites a control, that control cites
     the threat back. This is the check that catches drift as the document is
     edited.

Usage:
    python docs/research/verify_threat_coverage.py [path/to/THREAT_MODEL.md]

Exits non-zero on any violation.
"""

from __future__ import annotations

import collections
import pathlib
import re
import sys

DEFAULT_DOC = pathlib.Path(__file__).resolve().parents[1] / "THREAT_MODEL.md"

# Lookbehind matters: actor ids look like "AC-01", which contains "C-01".
THREAT_ID = re.compile(r"(?<![A-Za-z])T-\d{2}")
CONTROL_ID = re.compile(r"(?<![A-Za-z])C-\d{2}")
# A threat row opens with the threat id in bold; a control row opens with a bare id.
THREAT_ROW = re.compile(r"^\|\s*\*\*(T-\d{2})\*\*\s*\|")
CONTROL_ROW = re.compile(r"^\|\s*(C-\d{2})\s*\|")


def parse(doc: str) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Return (threat -> controls, control -> threats)."""
    threats: dict[str, set[str]] = collections.OrderedDict()
    controls: dict[str, set[str]] = collections.OrderedDict()

    for line in doc.splitlines():
        if m := THREAT_ROW.match(line):
            tid = m.group(1)
            threats.setdefault(tid, set()).update(CONTROL_ID.findall(line))
        elif m := CONTROL_ROW.match(line):
            cid = m.group(1)
            # Drop the control's own id before collecting the threats it cites.
            controls.setdefault(cid, set()).update(THREAT_ID.findall(line))

    return threats, controls


def main(argv: list[str]) -> int:
    path = pathlib.Path(argv[1]) if len(argv) > 1 else DEFAULT_DOC
    if not path.is_file():
        print(f"FAIL: {path} not found", file=sys.stderr)
        return 2

    threats, controls = parse(path.read_text(encoding="utf-8"))
    print(f"Parsed {len(threats)} threats and {len(controls)} controls from {path.name}\n")

    problems: list[str] = []

    uncontrolled = [t for t, cs in threats.items() if not cs]
    for t in uncontrolled:
        problems.append(f"BUG: threat {t} cites no control")

    orphaned = [c for c, ts in controls.items() if not ts]
    for c in orphaned:
        problems.append(f"SCOPE CREEP: control {c} cites no threat")

    # Referential integrity: cited ids must actually exist.
    for t, cs in threats.items():
        for c in sorted(cs - controls.keys()):
            problems.append(f"DANGLING: threat {t} cites {c}, which is not in the register")
    for c, ts in controls.items():
        for t in sorted(ts - threats.keys()):
            problems.append(f"DANGLING: control {c} cites {t}, which is not a defined threat")

    # Bidirectional agreement.
    for t, cs in threats.items():
        for c in sorted(cs & controls.keys()):
            if t not in controls[c]:
                problems.append(f"DRIFT: threat {t} cites {c}, but {c} does not cite {t} back")
    for c, ts in controls.items():
        for t in sorted(ts & threats.keys()):
            if c not in threats[t]:
                problems.append(f"DRIFT: control {c} cites {t}, but {t} does not cite {c} back")

    if problems:
        print(f"{len(problems)} problem(s):\n", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        return 1

    covered = sum(len(cs) for cs in threats.values())
    print(f"{len(threats)} threats, all controlled.")
    print(f"{len(controls)} controls, all justified by a threat.")
    print(f"{covered} threat-control links, agreeing in both directions.")
    print("\nThreat model coverage invariant holds.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
