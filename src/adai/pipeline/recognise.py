"""Stage 4: line recognition (ADR-0005).

STUB. Both tracks need a trained checkpoint and neither the Fidel corpus nor any
checkpoint is available in this environment:

* Track A -- CRNN + CTC over a flat syllable vocabulary (the baseline to beat).
* Track B -- factored decoding: separate heads for base consonant (37), vowel order (7)
  and labialisation, recombined through the Ethiopic grid. 44 classes cover 259
  syllables, which is the contribution (docs/RESEARCH.md section 5.2).

The stub returns EMPTY text, not placeholder Amharic. Fabricated transcription text
would be indistinguishable from a real result once it reached the database or the UI,
and that is exactly the silent fake this project forbids.
"""

from __future__ import annotations

import time

from adai.pipeline.types import LineSegmentation, RecognisedLine, RecognitionResult, StageResult

STAGE = "recognise"

STUB_REASON = (
    "No recogniser checkpoint. Track A (CRNN+CTC) and Track B (factored base x vowel "
    "decoding) both require training on Fidel, which is blocked -- see ADR-0008. "
    "Returns empty text rather than fabricated Amharic."
)


def recognise_lines(segmentation: LineSegmentation) -> RecognitionResult:
    started = time.perf_counter()
    lines = [
        RecognisedLine(line_id=line.id, text="", confidence=0.0) for line in segmentation.lines
    ]
    return RecognitionResult(
        result=StageResult(
            stage=STAGE,
            method="stub-empty",
            stub=True,
            stub_reason=STUB_REASON,
            duration_ms=(time.perf_counter() - started) * 1000,
        ),
        lines=lines,
    )
