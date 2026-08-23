"""Stage 5: reading order and structure assembly (ADR-0009).

Fully implemented -- this stage is pure logic and needs no model.

The JSON structure is the source of truth and the Markdown is derived from it. Markdown
loses bounding boxes, confidences and provenance, so it can never be the only artefact.
"""

from __future__ import annotations

import time

from adai.ethiopic.normalise import to_nfc
from adai.pipeline.types import (
    AssembledDocument,
    LayoutResult,
    LineSegmentation,
    RecognitionResult,
    RegionClass,
    StageResult,
)

STAGE = "assemble"

#: Characters that would change Markdown structure if they appeared in OCR output.
#: OCR text is attacker-controlled (threat T-04/T-12), so it is escaped here as well as
#: encoded at render time. Defence in depth, not a substitute for output encoding.
_MARKDOWN_ESCAPE = str.maketrans({c: "\\" + c for c in "\\`*_{}[]()#+-.!|<>"})


def escape_markdown(text: str) -> str:
    """Neutralise Markdown and HTML metacharacters in untrusted transcription text."""
    return text.translate(_MARKDOWN_ESCAPE)


def _render_region(cls: RegionClass, text: str) -> str:
    safe = escape_markdown(text)
    if cls is RegionClass.HEADING:
        return f"# {safe}"
    if cls is RegionClass.MARGINAL_NOTE:
        return f"> {safe}"
    if cls is RegionClass.PAGE_NUMBER:
        return ""  # metadata, not body text
    if cls is RegionClass.FIGURE:
        return "*[figure]*"
    if cls is RegionClass.TABLE:
        return safe
    return safe


def assemble(
    layout: LayoutResult,
    segmentation: LineSegmentation,
    recognition: RecognitionResult,
) -> AssembledDocument:
    """Serialise regions into reading order and emit Markdown + structured JSON."""
    started = time.perf_counter()

    text_by_line = {line.line_id: to_nfc(line.text) for line in recognition.lines}
    lines_by_region: dict[str, list[str]] = {}
    for line in sorted(segmentation.lines, key=lambda x: x.index_in_region):
        lines_by_region.setdefault(line.region_id, []).append(text_by_line.get(line.id, ""))

    ordered = sorted(layout.regions, key=lambda r: r.reading_order)

    regions_json: list[dict[str, object]] = []
    markdown_parts: list[str] = []
    for region in ordered:
        region_lines = lines_by_region.get(region.id, [])
        text = "\n".join(region_lines).strip()
        regions_json.append(
            {
                "id": region.id,
                "class": region.cls.value,
                "bbox": list(region.bbox),
                "reading_order": region.reading_order,
                "confidence": region.confidence,
                "text": text,
                "lines": region_lines,
            }
        )
        rendered = _render_region(region.cls, text)
        if rendered:
            markdown_parts.append(rendered)

    stages = [layout.result, segmentation.result, recognition.result]
    stages.append(
        StageResult(
            stage=STAGE,
            method="reading-order-serialisation",
            stub=False,
            duration_ms=(time.perf_counter() - started) * 1000,
        )
    )
    return AssembledDocument(
        markdown="\n\n".join(markdown_parts),
        regions=regions_json,
        stages=stages,
    )
