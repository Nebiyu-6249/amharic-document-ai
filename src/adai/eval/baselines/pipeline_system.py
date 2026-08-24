"""Our own five-stage pipeline, as a system under test."""

from __future__ import annotations

from adai.eval.types import EvalSample, SystemOutput
from adai.pipeline.runner import run_pipeline
from adai.pipeline.types import PageInput


class PipelineSystem:
    """Adapter around :func:`adai.pipeline.runner.run_pipeline`.

    Propagates the stub marker so the harness can refuse to present a stubbed run as a
    result. Right now every run is stubbed (ADR-0005), which is exactly why the marker
    has to survive all the way to the report.
    """

    name = "adai-pipeline"

    def transcribe(self, sample: EvalSample) -> SystemOutput:
        try:
            image_bytes = sample.image_path.read_bytes()
        except OSError as exc:
            return SystemOutput(text="", error=f"unreadable image: {exc}")

        try:
            from PIL import Image

            with Image.open(sample.image_path) as image:
                width, height = image.size
            document = run_pipeline(
                PageInput(blob_key=sample.id, width=width, height=height), image_bytes
            )
        except Exception as exc:
            return SystemOutput(text="", error=f"{type(exc).__name__}: {exc}")

        return SystemOutput(
            text=document.markdown,
            # regions is a JSONB-shaped dict, so values are object-typed; narrow
            # rather than casting, so a malformed region is skipped not crashed on.
            predicted_order=tuple(
                order
                for region in document.regions
                if isinstance(order := region.get("reading_order"), int)
            ),
            contains_stub_stages=document.contains_stub_stages,
        )
