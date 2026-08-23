"""The interchange schema between pipeline stages.

Versioned deliberately: stages are meant to be swapped, so the contract between them is
the thing that must stay stable. ADR-0001.
"""

from __future__ import annotations

import enum
from typing import Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION: Final[Literal["1"]] = "1"

#: (x0, y0, x1, y1) in pixels, origin top-left.
BBox = tuple[float, float, float, float]
Confidence = Annotated[float, Field(ge=0.0, le=1.0)]


class RegionClass(enum.StrEnum):
    PARAGRAPH = "paragraph"
    HEADING = "heading"
    TABLE = "table"
    FIGURE = "figure"
    MARGINAL_NOTE = "marginal_note"
    PAGE_NUMBER = "page_number"


class StageResult(BaseModel):
    """Common provenance carried by every stage output.

    ``stub`` is not decoration. It is how the project keeps its promise never to ship a
    silent fake: a stub stage marks its output, the marker is propagated by every
    downstream stage, and the API surfaces it.
    """

    model_config = ConfigDict(frozen=True)

    stage: str
    method: str
    stub: bool = False
    stub_reason: str | None = None
    duration_ms: float | None = None


class PageInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    blob_key: str
    width: int
    height: int


class RectifiedPage(BaseModel):
    """Stage 1 output: dewarped and illumination-corrected page."""

    model_config = ConfigDict(frozen=True)

    result: StageResult
    blob_key: str
    width: int
    height: int
    #: Max deviation in pixels of a known-straight reference line after rectification.
    #: This is the ADR-0002 acceptance measure; None when no reference was available.
    straightness_px: float | None = None
    illumination_corrected: bool = False


class Region(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    cls: RegionClass
    bbox: BBox
    #: Position in the page's reading order, 0-based. Scored with Kendall's tau.
    reading_order: int
    confidence: Confidence = 1.0
    #: Multi-point polygon for non-planar pages (PP-DocLayoutV3, ADR-0003).
    polygon: list[tuple[float, float]] | None = None


class LayoutResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    result: StageResult
    regions: list[Region] = Field(default_factory=list)


class TextLine(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    region_id: str
    bbox: BBox
    index_in_region: int
    baseline: list[tuple[float, float]] | None = None


class LineSegmentation(BaseModel):
    model_config = ConfigDict(frozen=True)

    result: StageResult
    lines: list[TextLine] = Field(default_factory=list)


class RecognisedLine(BaseModel):
    model_config = ConfigDict(frozen=True)

    line_id: str
    text: str
    confidence: Confidence = 0.0
    #: Populated only by the factored decoder (ADR-0005): per-position (base, vowel)
    #: predictions, which is what makes error attribution possible.
    factored: list[tuple[str, str]] | None = None


class RecognitionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    result: StageResult
    lines: list[RecognisedLine] = Field(default_factory=list)


class AssembledDocument(BaseModel):
    """Stage 5 output. The JSON is the source of truth; markdown is derived (ADR-0009)."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal["1"] = SCHEMA_VERSION
    markdown: str
    regions: list[dict[str, object]] = Field(default_factory=list)
    stages: list[StageResult] = Field(default_factory=list)

    @property
    def contains_stub_stages(self) -> bool:
        return any(s.stub for s in self.stages)
