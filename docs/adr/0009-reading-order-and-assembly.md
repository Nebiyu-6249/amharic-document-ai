# ADR-0009: Reading order from layout, assembly to Markdown/JSON, LM rescoring optional

**Status:** Accepted · **Date:** 2026-08-23

## Context
Stage 5 turns recognised lines plus classified regions into ordered, structured output. This is where the project's actual promise lives: the brief's whole framing is "structured, correctly-ordered output — not an unordered wall of characters."

Reading order is not a rendering detail. Perfect character recognition with inverted column order produces output that is 100% accurate per-character and useless to the reader. It therefore needs its own metric — **Kendall's tau** over the predicted vs. reference region sequence, not accuracy.

PP-DocLayoutV3 predicts reading order **jointly with layout in one pass** **[S]** (ADR-0003), which is a better signal than any post-hoc geometric sort because it is learned from document structure rather than inferred from coordinates.

## Decision
- **Primary order:** take PP-DocLayoutV3's predicted reading order.
- **Fallback:** a deterministic geometric sort (column detection → top-to-bottom within column) used when the layout model's order confidence is low, and as the comparison baseline so we can show the learned order is actually earning its place.
- **Assembly:** region class drives Markdown structure — heading → `#`, paragraph → prose, table → GFM table, figure → placeholder with bbox, marginal note → blockquote with a `marginalia` annotation, page number → metadata, not body text.
- **JSON output is the source of truth**; Markdown is derived from it. The JSON carries every region with bbox, class, reading-order index, per-line text, and per-line confidence. Markdown loses that and must never be the only artefact.
- **Table reconstruction** from cell coordinates, not from text heuristics.
- **LM rescoring over beam candidates is OPTIONAL and OFF by default**, behind a feature flag.

**On LM rescoring — a deliberate constraint.** An LM that "improves" Amharic OCR output can silently rewrite a student's exam answer or a ledger figure into something more probable but false. For documents containing grades and business records, a fluent wrong answer is worse than a visibly uncertain one. So: off by default; when on, it may only rescore among **beam candidates the recogniser actually produced** — never free-generate. Any rescored span is flagged in the JSON with both candidates retained.

## Alternatives rejected
| Alternative | Why rejected |
|---|---|
| Geometric sort only (XY-cut / column detection) | Fails on marginalia and complex tables — explicitly in scope. Retained as fallback and baseline. |
| Free-form LLM "clean up this OCR output" | Unbounded rewriting of untrusted content, and the OCR text is attacker-controlled (prompt injection, Phase 1 T-04). Categorically rejected on the request path. |
| Markdown as source of truth | Lossy — no bboxes, no confidences, no provenance. Cannot support the research or the UI. |
| Reading order as a post-hoc heuristic on line boxes | Discards the region-level structure that makes order tractable. |

## Consequences
- **Positive:** order is measured (Kendall's tau) rather than eyeballed; JSON preserves everything the UI and the research need.
- **Positive:** LM-off-by-default means the default output is faithful to the page.
- **Negative:** two output formats to keep in sync — mitigated by deriving one from the other.
- **Negative:** reading-order ground truth must be annotated to compute tau. That is real annotation work.

## Revisit when
Kendall's tau on the learned order fails to beat the geometric fallback, in which case the fallback becomes primary and we save a dependency.
