# ADR-0002: Use UVDoc directly; reject docuwarp

**Status:** Accepted · **Date:** 2026-08-23 · **Driver:** ML engineer + AppSec

## Context
Stage 1 needs dewarping. Three candidates were named: UVDoc, `pstwh/docuwarp` (ONNX UVDoc wrapper), DocTr.

`docuwarp` looked like the pragmatic choice — it is a packaged ONNX wrapper with CPU and CUDA extras, so it avoids reimplementing inference. Investigation disqualified it:

- **[V]** `LICENSE`, `LICENSE.md`, `LICENSE.txt`, `COPYING` all return **HTTP 404** on `main`; `setup.py` declares no `license=`. **No licence grant = all rights reserved.** Shipping it in an image is redistribution we have no right to perform.
- **[V]** Last release **2024-07-15** — two years stale. `python_requires=">=3.5, <4"` is meaningless metadata.
- **[P]** Hard-pins `pillow==10.4.0` (24 known CVEs, RESEARCH.md §3.3) and `onnxruntime==1.18.1`.
- **[P]** Vendors `.onnx` weights *inside the wheel* (`package_data={"docuwarp": ["artifacts/*.onnx"]}`) with no checksum — an unverifiable model blob delivered through PyPI.

Meanwhile **UVDoc itself is MIT licensed** (`LICENSE`, © 2023 Tanguy MAGNE) **[P]** — the upstream model the wrapper wraps is clean.

## Decision
Take the **UVDoc model under MIT**, and run our own ONNX Runtime inference wrapper (a small, well-understood amount of code). Pair it with a separate illumination-correction step (CLAHE-based local contrast normalisation) rather than adopting DocTr wholesale.

Acceptance is **quantitative**, per the brief: photograph ruled paper, fit a line to a known-straight rule before and after, and assert max deviation from the fitted line drops below a threshold. A dewarper that does not straighten a straight line fails, regardless of how good the output looks.

## Alternatives rejected
| Alternative | Why rejected |
|---|---|
| `pstwh/docuwarp` | No licence (blocker), stale, CVE-laden pins, unverified vendored weights. |
| DocTr as a dependency | Research repo, not packaged for production; its illumination correction is valuable as an *idea*, and we implement that idea directly. |
| OpenCV four-point perspective transform only | Corrects planar perspective, not the *curl* of a page held in the hand. Fails the ruled-line acceptance test on curved pages. Kept as a cheap fallback when UVDoc's confidence is low. |
| No dewarping; train the recogniser to be warp-invariant | Pushes an unsolved geometry problem into the recogniser and destroys the diacritic signal we specifically need to preserve. |

## Consequences
- **Positive:** clean MIT licence; we control the inference path; onnxruntime version is ours to keep current (`1.29.0`, requires Python ≥3.11 — consistent with our 3.11 target).
- **Negative:** we own the preprocessing/postprocessing code that `docuwarp` would have given us. Small, but real.
- We must obtain UVDoc weights and **pin them by checksum** — the weights are not on PyPI, and the checksum requirement is non-negotiable (RESEARCH.md §7).

## Revisit when
A maintained, properly licensed UVDoc packaging appears, or dewarping proves not to be the binding constraint on end-to-end accuracy.
