"""Types shared by the evaluation harness.

The harness is deliberately generic over the thing being evaluated: our own pipeline and
an off-the-shelf VLM must be measured by exactly the same code on exactly the same
samples, or the comparison in ADR-0010 means nothing.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable


class Corpus(enum.StrEnum):
    """Which corpus a sample came from.

    Kept on every sample because WER is reported **per corpus** and never pooled:
    classical Ge'ez is `፡`-delimited and modern Amharic is space-delimited, so a single
    averaged WER is meaningless (ADR-0006).
    """

    FIDEL = "fidel"
    HHD_ETHIOPIC = "hhd_ethiopic"
    CAPTURED = "captured"
    SYNTHETIC = "synthetic"


class CaptureCondition(enum.StrEnum):
    """How the image was produced. Drives the unseen-capture-condition split."""

    SCAN = "scan"
    PHONE_FLAT = "phone_flat"
    PHONE_WARPED = "phone_warped"
    PHONE_SHADOW = "phone_shadow"
    RULED_PAPER = "ruled_paper"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class EvalSample:
    """One evaluated item, with everything any metric needs."""

    id: str
    image_path: Path
    reference_text: str
    corpus: Corpus
    #: Required for the unseen-writer split. None for printed or synthetic material.
    writer_id: str | None = None
    capture_condition: CaptureCondition = CaptureCondition.UNKNOWN
    #: (class, bbox) pairs for layout mAP. Empty when the sample is line-level.
    reference_regions: tuple[tuple[str, tuple[float, float, float, float]], ...] = ()
    #: Region ids in true reading order, for Kendall's tau.
    reference_order: tuple[int, ...] = ()
    #: Field-level ground truth for end-to-end F1 (e.g. {"name": ..., "grade": ...}).
    reference_fields: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SystemOutput:
    """What a system under test produced for one sample."""

    text: str
    predicted_regions: tuple[tuple[str, tuple[float, float, float, float], float], ...] = ()
    predicted_order: tuple[int, ...] = ()
    predicted_fields: dict[str, str] = field(default_factory=dict)
    #: True when any stage was a stub. A run containing stubs is not a result.
    contains_stub_stages: bool = False
    error: str | None = None


@runtime_checkable
class RecognitionSystem(Protocol):
    """Anything the harness can measure: our pipeline, surya, a frontier VLM."""

    name: str

    def transcribe(self, sample: EvalSample) -> SystemOutput:
        """Return the system's output for one sample. Must not raise for a bad sample;
        return SystemOutput(error=...) instead so one failure does not void the run."""
        ...
