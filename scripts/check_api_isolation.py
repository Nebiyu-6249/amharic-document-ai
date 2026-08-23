#!/usr/bin/env python3
"""Enforce control C-45: the API image must contain no ML stack.

ADR-0007 exists because `surya-ocr` hard-caps `pillow<11`, which forces pillow 10.4.0 --
a release carrying 24 known CVEs -- onto the exact code path that decodes hostile
uploads. Keeping those dependencies apart is an architectural boundary, so it is checked
by CI rather than left to reviewer memory.

Two checks:
  1. the api lockfile contains no forbidden distribution;
  2. the api lockfile pins pillow at or above the safe floor.

Usage: python scripts/check_api_isolation.py [requirements/api.lock.txt]
"""

from __future__ import annotations

import pathlib
import re
import sys

FORBIDDEN = {
    "torch",
    "torchvision",
    "surya-ocr",
    "paddlepaddle",
    "paddleocr",
    "paddlex",
    "kraken",
    "onnxruntime",
    "onnxruntime-gpu",
    "opencv-python",
    "opencv-contrib-python",
}

#: pillow < 12.1.1 carries known CVEs; 12.3.0 is the floor we lock to.
MIN_PILLOW = (12, 3, 0)

PIN = re.compile(r"^([A-Za-z0-9._-]+)==([0-9][^\s;]*)")


def main(argv: list[str]) -> int:
    path = pathlib.Path(argv[1] if len(argv) > 1 else "requirements/api.lock.txt")
    if not path.is_file():
        print(f"FAIL: {path} not found", file=sys.stderr)
        return 2

    pins: dict[str, str] = {}
    for line in path.read_text().splitlines():
        if match := PIN.match(line.strip()):
            pins[match.group(1).lower().replace("_", "-")] = match.group(2)

    problems: list[str] = []

    for name in sorted(FORBIDDEN & pins.keys()):
        problems.append(
            f"{name}=={pins[name]} must not be in the api image (ADR-0007 / control C-45)"
        )

    pillow = pins.get("pillow")
    if pillow is None:
        problems.append("pillow is not pinned in the api lockfile")
    else:
        parts = tuple(int(p) for p in re.findall(r"\d+", pillow)[:3])
        if parts < MIN_PILLOW:
            problems.append(
                f"pillow=={pillow} is below the {'.'.join(map(str, MIN_PILLOW))} floor; "
                "pillow 10.4.0 has 24 known CVEs and decodes hostile uploads"
            )

    if problems:
        print(f"C-45 VIOLATION ({len(problems)}):", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    print(f"C-45 holds: {len(pins)} pins, no ML stack, pillow=={pillow}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
