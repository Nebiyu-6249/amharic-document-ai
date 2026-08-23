"""Pipeline stages and the no-silent-fakes invariant (ADR-0001)."""

from __future__ import annotations

import io

import numpy as np
from PIL import Image

from adai.pipeline.assemble import assemble, escape_markdown
from adai.pipeline.layout import analyse_layout
from adai.pipeline.lines import segment_lines
from adai.pipeline.recognise import recognise_lines
from adai.pipeline.rectify import background_uniformity, correct_illumination, rectify
from adai.pipeline.runner import run_pipeline
from adai.pipeline.types import PageInput


def _page(width: int = 300, height: int = 200) -> tuple[PageInput, bytes]:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (240, 240, 235)).save(buf, "JPEG")
    return PageInput(blob_key="k", width=width, height=height), buf.getvalue()


# --- stage 1: illumination correction is REAL and must measurably work -------------


def test_illumination_correction_flattens_a_shadow_gradient() -> None:
    """A page half in shadow must come out with a roughly uniform background.

    This is the quantitative acceptance test for the implemented half of stage 1.
    """
    width, height = 200, 120
    gradient = np.tile(np.linspace(40, 255, width, dtype=np.uint8), (height, 1))
    shadowed = Image.fromarray(gradient, mode="L").convert("RGB")

    before = background_uniformity(shadowed)
    after = background_uniformity(correct_illumination(shadowed))

    assert before > 20, "test fixture does not actually have a gradient"
    assert after < before / 2, f"illumination not flattened: {before:.1f} -> {after:.1f}"


def test_rectify_reports_dewarping_as_not_implemented() -> None:
    page, data = _page()
    rectified, _ = rectify(page, data)
    assert rectified.illumination_corrected is True
    assert rectified.result.stub is True
    assert "dewarp" in (rectified.result.stub_reason or "").lower()
    # No reference line was supplied, so no straightness claim may be made.
    assert rectified.straightness_px is None


# --- stages 2-4 are stubs and must say so ------------------------------------------


def test_stub_stages_are_all_marked() -> None:
    page, data = _page()
    rectified, _ = rectify(page, data)
    layout = analyse_layout(rectified)
    segmentation = segment_lines(layout)
    recognition = recognise_lines(segmentation)
    for result in (layout.result, segmentation.result, recognition.result):
        assert result.stub is True
        assert result.stub_reason


def test_recogniser_returns_empty_text_not_fabricated_amharic() -> None:
    """A stub that invented plausible text would be indistinguishable from a result."""
    page, data = _page()
    rectified, _ = rectify(page, data)
    recognition = recognise_lines(segment_lines(analyse_layout(rectified)))
    assert all(line.text == "" for line in recognition.lines)
    assert all(line.confidence == 0.0 for line in recognition.lines)


# --- stage 5: assembly is REAL ------------------------------------------------------


def test_assemble_orders_regions_by_reading_order() -> None:
    from adai.pipeline.types import (
        LayoutResult,
        LineSegmentation,
        RecognisedLine,
        RecognitionResult,
        Region,
        RegionClass,
        StageResult,
        TextLine,
    )

    ok = StageResult(stage="t", method="t")
    regions = [
        Region(id="b", cls=RegionClass.PARAGRAPH, bbox=(0, 0, 1, 1), reading_order=1),
        Region(id="a", cls=RegionClass.HEADING, bbox=(0, 0, 1, 1), reading_order=0),
    ]
    lines = [
        TextLine(id="a-l0", region_id="a", bbox=(0, 0, 1, 1), index_in_region=0),
        TextLine(id="b-l0", region_id="b", bbox=(0, 0, 1, 1), index_in_region=0),
    ]
    recognised = [
        RecognisedLine(line_id="a-l0", text="Title", confidence=1.0),
        RecognisedLine(line_id="b-l0", text="Body", confidence=1.0),
    ]
    doc = assemble(
        LayoutResult(result=ok, regions=regions),
        LineSegmentation(result=ok, lines=lines),
        RecognitionResult(result=ok, lines=recognised),
    )
    assert [r["id"] for r in doc.regions] == ["a", "b"]
    assert doc.markdown.startswith("# Title")


def test_ocr_text_is_escaped_before_entering_markdown() -> None:
    """OCR output is attacker-controlled (T-04/T-12)."""
    assert "<script>" not in escape_markdown("<script>alert(1)</script>")
    assert escape_markdown("# not a heading").startswith("\\#")


# --- end to end ---------------------------------------------------------------------


def test_full_pipeline_propagates_stub_marker() -> None:
    page, data = _page()
    doc = run_pipeline(page, data)
    assert doc.contains_stub_stages is True
    assert {s.stage for s in doc.stages} == {"rectify", "layout", "lines", "recognise", "assemble"}
    assert doc.schema_version == "1"
