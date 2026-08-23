# ADR-0001: Five-stage pipeline, not an end-to-end model

**Status:** Accepted · **Date:** 2026-08-23 · **Driver:** Staff ML engineer

## Context
The unsolved problem is the *full page under real capture conditions* — warp, shadow, ruled paper, multi-column, tables, reading order. Line-level recognition on clean crops is already solved and must not be rebuilt.

An end-to-end page→Markdown model is attractive and is what modern document VLMs do. But it has one property that is disqualifying at this stage: **when it is wrong, you cannot tell which part is wrong.** If a page comes out garbled, an end-to-end model gives no signal distinguishing "dewarping failed" from "reading order inverted" from "the vowel diacritic was misread".

The project's central thesis — that the few-pixel vowel diacritic is the core difficulty (RESEARCH.md §5.2) — is only testable if recognition is isolated and independently measurable.

## Decision
Five independently testable stages with clean interfaces:

1. Geometric rectification (dewarp + illumination)
2. Layout analysis (region detect + classify)
3. Line segmentation (baseline detection within regions)
4. Line recognition (two tracks: flat CTC baseline, factored contribution)
5. Reading order + structure assembly → Markdown/JSON

Each stage has its own acceptance metric and can be swapped without touching its neighbours. Each is a separate Python module with a typed interface.

## Alternatives rejected
| Alternative | Why rejected |
|---|---|
| End-to-end page→Markdown VLM as the primary system | Unfalsifiable failure attribution; cannot isolate the diacritic hypothesis; requires page-level training data we do not have. **Kept as a Phase 6 baseline (ADR-0010), not as the system.** |
| Two stages (detect+recognise) as in classic OCR | Collapses layout, reading order and structure into one; those are precisely the unsolved parts. |
| Start end-to-end, decompose later | Decomposition after the fact means rebuilding, and the intermediate never gets ground truth. |

## Consequences
- **Positive:** every stage independently ablatable; failures localise; stages can be built and tested in parallel; a weak stage can be replaced by an off-the-shelf component without redesign.
- **Negative:** error compounds across stages — a 95% stage-1 and 95% stage-3 give 90% together. We must measure per-stage *and* end-to-end (Phase 6 requires both).
- **Negative:** more interfaces to maintain than a single model.
- Commits us to defining and versioning an intermediate page-representation schema between stages.

## Revisit when
An off-the-shelf VLM beats the assembled pipeline end-to-end on our unseen-capture-condition split (ADR-0010). At that point the pipeline's value is diagnostic, not productive, and we should say so.
