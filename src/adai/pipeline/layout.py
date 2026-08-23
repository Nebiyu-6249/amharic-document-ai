"""Stage 2: layout analysis (ADR-0003).

STUB. The chosen model is PP-DocLayoutV3, which needs paddlepaddle and downloaded
weights in the isolated worker-layout container (control C-45). Neither is installed in
the environment that produced this repo, and ADR-0003 is still Provisional because the
weight format and licence could not be verified (Hugging Face is egress-blocked).

The stub returns a single page-sized paragraph region so downstream stages have a
well-formed input to exercise, and marks itself so the placeholder cannot be mistaken
for analysis.
"""

from __future__ import annotations

import time

from adai.pipeline.types import LayoutResult, RectifiedPage, Region, RegionClass, StageResult

STAGE = "layout"

STUB_REASON = (
    "PP-DocLayoutV3 not wired: requires the isolated worker-layout container "
    "(paddlepaddle) plus checksum-verified weights. ADR-0003 is Provisional pending "
    "weight-format and licence verification."
)


def analyse_layout(page: RectifiedPage) -> LayoutResult:
    started = time.perf_counter()
    region = Region(
        id="r0",
        cls=RegionClass.PARAGRAPH,
        bbox=(0.0, 0.0, float(page.width), float(page.height)),
        reading_order=0,
        confidence=0.0,
    )
    return LayoutResult(
        result=StageResult(
            stage=STAGE,
            method="stub-single-region",
            stub=True,
            stub_reason=STUB_REASON,
            duration_ms=(time.perf_counter() - started) * 1000,
        ),
        regions=[region],
    )
