"""Chain the five stages end to end."""

from __future__ import annotations

from adai.pipeline.assemble import assemble
from adai.pipeline.layout import analyse_layout
from adai.pipeline.lines import segment_lines
from adai.pipeline.recognise import recognise_lines
from adai.pipeline.rectify import rectify
from adai.pipeline.types import AssembledDocument, PageInput


def run_pipeline(page: PageInput, image_bytes: bytes) -> AssembledDocument:
    """Run stages 1-5. Stub markers from any stage propagate into the result."""
    rectified, rectified_bytes = rectify(page, image_bytes)
    del rectified_bytes  # persisted by the caller in the full implementation
    layout = analyse_layout(rectified)
    segmentation = segment_lines(layout)
    recognition = recognise_lines(segmentation)
    document = assemble(layout, segmentation, recognition)
    return AssembledDocument(
        markdown=document.markdown,
        regions=document.regions,
        stages=[rectified.result, *document.stages],
    )
