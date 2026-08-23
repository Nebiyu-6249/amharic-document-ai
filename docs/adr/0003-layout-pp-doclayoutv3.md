# ADR-0003: PP-DocLayoutV3 for layout analysis, in an isolated container

**Status:** Provisional (pending weight/licence verification) · **Date:** 2026-08-23

## Context
Stage 2 must detect and classify regions (paragraph, heading, table, figure, marginal note, page number) on **non-planar, phone-captured** pages, and ideally produce reading order.

PP-DocLayoutV3 is built for exactly this: it predicts **multi-point boxes** (instance masks rather than axis-aligned rectangles) and **reading order** in a single pass, explicitly targeting skewed/curved/photographed pages **[S]**. Reported ~92.5% at 132 FPS with 33M params **[S]**. PaddleOCR is Apache-2.0 **[P]**.

The concern the brief raised — is PaddlePaddle an acceptable dependency or a liability? — is real. It is an entire second deep-learning framework alongside torch.

**Measured [V]:** `paddleocr + paddlepaddle + torch` **does co-install** (256 packages resolved). So it is not a hard conflict. But `paddlepaddle` declares **no `requires_python`** **[V]**, which means the resolver offers us no protection against a bad future version.

## Decision
Adopt **PP-DocLayoutV3 for layout + reading order**, but:

1. Run it in its **own container** with its own pinned environment. It never shares a Python environment with the API (ADR-0007) or with the torch-based recogniser.
2. Pin `paddlepaddle` and `paddleocr` to **exact versions** (`3.3.1`, `3.7.0`), because the metadata will not protect us.
3. Communicate with it over a narrow, typed interface (regions + order), so replacing it means reimplementing one adapter.
4. Use **only the layout model**. PaddleOCR's *recognition* does not list Amharic **[P]** and is not used.

## Alternatives rejected
| Alternative | Why rejected |
|---|---|
| surya layout | Weights are OpenRAIL-M with a $5M ceiling **[P]**, and surya forces `pillow<11` with 24 CVEs **[V]**. Unacceptable for a load-bearing stage. |
| kraken's trainable layout | Strong and Apache-2.0 — genuinely the runner-up. Rejected for *layout* because it is not built for non-planar photographed pages and has no equivalent multi-point/reading-order joint prediction. **We do use kraken for line segmentation (ADR-0004).** |
| Train our own layout model | No annotated Ethiopic page-layout corpus exists. This is scope we cannot afford. |
| Heuristic layout (connected components + column detection) | Fails on marginalia and tables, which are explicitly in scope. |

## Consequences
- **Positive:** purpose-built for our hardest capture conditions; gets reading order for free from the same pass; Apache-2.0 code.
- **Negative:** a second DL framework in the system (container-isolated, but still a build/ops cost and a large image).
- **Negative:** ties a core stage to a vendor's release cadence with weak version metadata.
- **Open:** weight format and weight licence unverified — HF and Paddle docs both egress-blocked (RESEARCH.md §8 Q6). A `PP-DocLayoutV3_safetensors` repo appears to exist **[S]**; if the weights turn out to be pickle-only, ADR-0007's safetensors-only rule forces reconsideration.

## Revisit when
Weight licence/format verification fails, or the isolated container proves too costly to operate. Fallback is kraken layout + a geometric reading-order heuristic.
