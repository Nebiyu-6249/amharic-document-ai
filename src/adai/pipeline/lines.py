"""Stage 3: line segmentation (ADR-0004).

STUB. The chosen approach is kraken's trainable baseline detection (``blla``), which
lives in the ml extra and is not installed here.

Note what this stub does NOT do: it does not fall back to projection profiles. ADR-0004
rejects them for this corpus because a projection profile cannot distinguish a ruled
line from a line of text -- both are simply "a row with a lot of dark pixels" -- and
ruled paper is a target document type. A fallback that is known-wrong for the target
data would be worse than an honest stub.
"""

from __future__ import annotations

import time

from adai.pipeline.types import LayoutResult, LineSegmentation, StageResult, TextLine

STAGE = "lines"

STUB_REASON = (
    "kraken baseline segmentation (blla) not wired: requires the ml extra in the "
    "worker-ocr container. Deliberately does NOT fall back to projection profiles, "
    "which ADR-0004 rejects for ruled paper."
)


def segment_lines(layout: LayoutResult) -> LineSegmentation:
    started = time.perf_counter()
    lines = [
        TextLine(id=f"{region.id}-l0", region_id=region.id, bbox=region.bbox, index_in_region=0)
        for region in layout.regions
    ]
    return LineSegmentation(
        result=StageResult(
            stage=STAGE,
            method="stub-one-line-per-region",
            stub=True,
            stub_reason=STUB_REASON,
            duration_ms=(time.perf_counter() - started) * 1000,
        ),
        lines=lines,
    )
