# ADR-0010: A general-purpose VLM baseline runs from day one

**Status:** Accepted · **Date:** 2026-08-23 · **Driver:** Pragmatic tech lead

## Context
This is the ADR that could cancel the project, which is exactly why it is written down.

**[P]** surya's own multilingual table lists **`am` Amharic at 74.6%**. The brief was written assuming Ethiopic is largely unserved by off-the-shelf tooling. At least one general-purpose system already claims non-trivial Amharic capability.

That figure is *not* a CER and not comparable to one — it is surya's internal pass/fail metric on their benchmark, undefined for our documents. It does not tell us whether surya handles a warped, shadowed, ruled-paper exam paper. **But it is enough to make "does an off-the-shelf VLM already solve this?" a live question rather than a rhetorical one.**

Building a five-stage pipeline for a year and *then* discovering a commodity VLM matches it would be the single most expensive failure available to this project.

## Decision
Build the **VLM baseline runner in Phase 6 alongside the first pipeline stage — not at the end.** It evaluates general-purpose vision-language models on the identical benchmark, identical splits, identical metrics (CER, normalisation-aware CER, WER, NED, reading-order tau, field-level F1).

At minimum: **surya** (quarantined per ADR-0007) and at least one frontier general-purpose VLM.

**This baseline is a decision gate, and the honest outcomes are enumerated in advance:**
- If the pipeline beats the VLM on unseen-capture-condition → the project is justified; continue.
- If the VLM matches or beats it → **say so loudly and immediately.** The contribution then narrows to the factored-decoding result (ADR-0005) and the security/application layer, and the pipeline is reframed as a diagnostic instrument. That is still a legitimate outcome; pretending otherwise is not.

Constraints: runs **offline against the evaluation corpus only**, never on the request path, never on user uploads. Costs are capped by the same quota mechanism as production AI calls (Phase 5).

## Alternatives rejected
| Alternative | Why rejected |
|---|---|
| Build the pipeline first, benchmark at the end | Maximum sunk cost before the load-bearing question is answered. This is the failure mode the decision exists to prevent. |
| Assume off-the-shelf VLMs cannot do Ethiopic | Contradicted by surya's own published table **[P]**. Assuming it would be wishful. |
| Use the VLM as the product | Does not test the diacritic hypothesis, gives no failure attribution (ADR-0001), and puts an unbounded generative model on untrusted document text (T-04). |
| Benchmark surya only | One system is not a baseline; it is an anecdote. |

## Consequences
- **Positive:** we know from early on whether the work is warranted, and can redirect while redirection is still cheap.
- **Positive:** a strong VLM baseline strengthens any eventual writeup — a contribution measured against a real competitor is worth more than one measured against a strawman.
- **Negative:** engineering effort before the pipeline exists, and API spend on evaluation runs (capped).
- **Negative:** the surya container carries `pillow==10.4.0` with 24 CVEs **[V]**. Tolerable **only** because it is offline, air-gapped from user data, and never on the request path (ADR-0007).

## Revisit when
Never fully — this runs on every evaluation cycle, not once. Re-examine the model roster as new VLMs ship.
