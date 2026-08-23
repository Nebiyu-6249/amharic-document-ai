"""Stage 1: geometric rectification and illumination correction (ADR-0002).

Two halves with very different maturity, and they are kept separate so the honest one
is usable now:

* **Illumination correction is implemented.** It divides the page by an estimated
  background field, which is the standard fix for the shadow gradient that makes global
  Otsu thresholding fail (over-threshold in the bright region, under-threshold in the
  shadow). Pure numpy + Pillow, no heavy dependency.
* **Dewarping is a stub.** It needs UVDoc weights, which are not vendored (ADR-0002
  rejected docuwarp over its missing licence, and the MIT UVDoc weights must be fetched
  and checksummed separately). The stub marks its output rather than pretending.
"""

from __future__ import annotations

import io
import time

import numpy as np
from PIL import Image

from adai.pipeline.types import PageInput, RectifiedPage, StageResult

STAGE = "rectify"


def estimate_background(gray: np.ndarray, *, downsample: int = 16) -> np.ndarray:
    """Estimate the slowly-varying illumination field of a page.

    Downsample hard (which averages away text strokes but keeps the lighting gradient),
    smooth, then resize back. What survives is the shadow/flash field, not the ink.
    """
    h, w = gray.shape
    small_h = max(1, h // downsample)
    small_w = max(1, w // downsample)
    small = np.asarray(
        Image.fromarray(gray).resize((small_w, small_h), Image.Resampling.BILINEAR),
        dtype=np.float32,
    )
    # A couple of box-blur passes: cheap, and enough for a smooth field.
    for _ in range(2):
        padded = np.pad(small, 1, mode="edge")
        small = (
            padded[:-2, 1:-1] + padded[2:, 1:-1] + padded[1:-1, :-2] + padded[1:-1, 2:] + small
        ) / 5.0
    return np.asarray(
        Image.fromarray(small.astype(np.uint8)).resize((w, h), Image.Resampling.BILINEAR),
        dtype=np.float32,
    )


def correct_illumination(image: Image.Image) -> Image.Image:
    """Flatten a non-uniform illumination field.

    Divides by the estimated background and rescales. A page photographed half in
    shadow comes out with a roughly uniform background, which is what every downstream
    threshold and every recogniser expects.
    """
    gray = np.asarray(image.convert("L"), dtype=np.uint8)
    background = estimate_background(gray)
    # Avoid division by zero in genuinely black regions.
    background = np.maximum(background, 1.0)
    normalised = (gray.astype(np.float32) / background) * float(np.mean(background))
    clipped = np.clip(normalised, 0, 255).astype(np.uint8)
    return Image.fromarray(clipped, mode="L").convert("RGB")


def background_uniformity(image: Image.Image) -> float:
    """Std-dev of the estimated illumination field. Lower is flatter.

    This is the quantitative handle the acceptance test uses: correcting a synthetic
    gradient must reduce this number substantially.
    """
    gray = np.asarray(image.convert("L"), dtype=np.uint8)
    return float(np.std(estimate_background(gray)))


def rectify(page: PageInput, image_bytes: bytes) -> tuple[RectifiedPage, bytes]:
    """Run stage 1. Illumination correction is real; dewarping is not yet wired."""
    started = time.perf_counter()
    with Image.open(io.BytesIO(image_bytes)) as src:
        src.load()
        corrected = correct_illumination(src)

    out = io.BytesIO()
    corrected.save(out, format="JPEG", quality=92)

    result = StageResult(
        stage=STAGE,
        method="illumination-division",
        stub=True,
        stub_reason=(
            "Illumination correction is implemented; geometric dewarping is NOT. "
            "UVDoc weights (MIT, ADR-0002) are not vendored and must be fetched and "
            "checksum-verified before stage 1 is complete."
        ),
        duration_ms=(time.perf_counter() - started) * 1000,
    )
    return (
        RectifiedPage(
            result=result,
            blob_key=page.blob_key,
            width=corrected.width,
            height=corrected.height,
            straightness_px=None,
            illumination_corrected=True,
        ),
        out.getvalue(),
    )
