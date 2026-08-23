"""The five-stage document pipeline (ADR-0001).

Stages are independently testable and swappable. Each declares whether it is a real
implementation or a stub; a stub NEVER silently returns plausible output -- it sets
``stub=True`` and a ``stub_reason`` that propagates all the way to the API response and
the database, so nothing downstream can mistake placeholder data for a transcription.
"""

from adai.pipeline.types import (
    AssembledDocument,
    LayoutResult,
    LineSegmentation,
    PageInput,
    RecognitionResult,
    RectifiedPage,
    Region,
    RegionClass,
    StageResult,
    TextLine,
)

__all__ = [
    "AssembledDocument",
    "LayoutResult",
    "LineSegmentation",
    "PageInput",
    "RecognitionResult",
    "RectifiedPage",
    "Region",
    "RegionClass",
    "StageResult",
    "TextLine",
]
