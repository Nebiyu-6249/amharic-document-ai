"""surya as a baseline (ADR-0010).

surya's own multilingual table lists Amharic at **74.6%** on their internal benchmark.
That figure is not a CER and says nothing about warped, shadowed, ruled-paper pages --
but it is enough to make "does an off-the-shelf system already solve this?" a live
question rather than a rhetorical one, which is why this baseline exists.

Two constraints, both non-negotiable:

* **Offline only.** surya forces ``pillow 10.4.0``, which carries 24 known CVEs, so it
  lives in a quarantined container that never sees a user upload and has no route from
  the request handler (ADR-0007, residual risk R-01).
* **Weights are not open source.** Modified AI Pubs OpenRAIL-M with a $5M
  funding/revenue ceiling. Fine for research; a tripwire if this ever commercialises.
  surya must never become a load-bearing production dependency.

surya is not installed in the default environment. This adapter reports that clearly
rather than failing obscurely at the first sample.
"""

from __future__ import annotations

from adai.eval.types import EvalSample, SystemOutput


class SuryaUnavailableError(RuntimeError):
    """surya is not installed in this environment."""


class SuryaBaseline:
    """Adapter around surya's OCR predictor."""

    name = "surya"

    def __init__(self) -> None:
        try:  # pragma: no cover - depends on an optional, quarantined install
            import surya  # noqa: F401
        except ImportError as exc:
            raise SuryaUnavailableError(
                "surya is not installed.\n"
                "\n"
                "It is deliberately NOT in the default environment: it forces "
                "pillow 10.4.0 (24 known CVEs) onto whatever process imports it, so it "
                "belongs only in the quarantined baseline-vlm container "
                "(ADR-0007 / control C-45).\n"
                "\n"
                "To run this baseline, build that container and invoke the harness "
                "inside it. Never add surya to the api or worker image."
            ) from exc

    def transcribe(self, sample: EvalSample) -> SystemOutput:  # pragma: no cover
        from surya.recognition import RecognitionPredictor

        predictor = RecognitionPredictor()
        try:
            from PIL import Image

            with Image.open(sample.image_path) as image:
                predictions = predictor([image], [["am"]])
        except Exception as exc:
            return SystemOutput(text="", error=f"{type(exc).__name__}: {exc}")

        lines = [line.text for page in predictions for line in page.text_lines]
        return SystemOutput(text="\n".join(lines))
