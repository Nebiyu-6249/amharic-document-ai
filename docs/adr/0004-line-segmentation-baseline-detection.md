# ADR-0004: Baseline-detection line segmentation (kraken), not projection profiles

**Status:** Accepted · **Date:** 2026-08-23

## Context
The brief states projection profiles are unacceptable for handwriting and invites disagreement. **I agree, and the reasoning is worth recording rather than asserting.**

A horizontal projection profile sums ink per row and cuts at minima. It assumes (a) lines are straight and horizontal, (b) lines do not overlap vertically, (c) the darkest rows are text. Real Ethiopian handwriting on phone photos violates all three:

- Residual curvature survives dewarping, so a "row" crosses two text lines at the page edges.
- Ascenders/descenders and labialised forms interleave between lines.
- **Ruled paper puts a hard horizontal ink maximum exactly where the profile expects a text line** (RESEARCH.md §6, difficulty 6). A projection profile cannot distinguish a rule from a line of text — they are both "lots of dark pixels in a row". This alone is disqualifying for our target documents.

kraken is a strong fit: **Apache-2.0** **[P]**, `requires-python >=3.10,<3.14` **[P]**, actively maintained (7.1, released 2026-08-04 — three weeks old **[V]**), explicitly built for "historical and non-Latin script material", with **trainable** baseline segmentation (`blla`) plus layout and reading order. It accepts `pillow>=12` **[V]** — no CVE-laden pin.

## Decision
Use **kraken's baseline-detection segmentation (`blla`)** within the regions produced by stage 2. Fine-tune on Ethiopic handwriting as annotated data becomes available; use **eScriptorium** as the annotation UI (it is the companion tool over the same model format), but **not** as a runtime dependency.

## Alternatives rejected
| Alternative | Why rejected |
|---|---|
| Horizontal projection profiles | Cannot distinguish ruled lines from text lines; assumes straight, non-overlapping, horizontal lines. Fails on the target corpus by construction. |
| ARU-Net | The idea (U-Net baseline detection) is sound and is what `blla` descends from, but the official implementation is TF1-era and **does not polygonise its output** **[S]** — we would have to write the polygonisation ourselves. kraken ships that. |
| surya line detection | OpenRAIL-M weights + `pillow<11` (24 CVEs) **[V]**. Same rejection as ADR-0003. |
| Train our own from scratch | kraken's `blla` is a fine-tunable starting point; starting from zero wastes the transfer. |

## Consequences
- **Positive:** Apache-2.0, no weight-licence encumbrance, actively maintained, purpose-built for non-Latin/historical, trainable on our data, astral-plane-safe text handling.
- **Positive:** eScriptorium gives us an annotation path without building one.
- **Negative:** adds `lightning==2.6.1` and a large torch dependency tree (284 packages resolved **[V]**) to the recognition container.
- **Negative:** fine-tuning needs annotated baselines, which we do not yet have. Until then we run the stock model and measure the gap.

## Revisit when
Stock `blla` proves unable to separate text from ruled lines even after fine-tuning; then rule-suppression moves earlier, into stage 1.
