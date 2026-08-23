# Architecture Decision Records

One record per significant choice, each naming the alternatives rejected and why.
Evidence tags (`[V]` verified by execution, `[P]` primary source read, `[S]` secondary
only, `[BLOCKED]` unverifiable here) are defined in [../RESEARCH.md](../RESEARCH.md) §0.

| ADR | Decision | Status |
|---|---|---|
| [0001](0001-staged-pipeline-not-end-to-end.md) | Five-stage pipeline, not an end-to-end model | Accepted |
| [0002](0002-dewarping-uvdoc-direct.md) | UVDoc (MIT) directly; reject docuwarp (no licence) | Accepted |
| [0003](0003-layout-pp-doclayoutv3.md) | PP-DocLayoutV3 for layout, isolated container | **Provisional** |
| [0004](0004-line-segmentation-baseline-detection.md) | kraken baseline detection, not projection profiles | Accepted |
| [0005](0005-recognition-factored-decoding.md) | CRNN+CTC baseline + factored base×vowel decoding | Accepted |
| [0006](0006-ethiopic-normalisation-and-tokenisation.md) | Charset, homophone folding, `[\s፡]+` tokenisation | Accepted |
| [0007](0007-process-isolation-of-ml-stacks.md) | API and ML stacks never share a Python environment | Accepted |
| [0008](0008-dataset-strategy.md) | Fidel primary, HHD pretraining only | **Accepted, blocked on Fidel access** |
| [0009](0009-reading-order-and-assembly.md) | Reading order from layout; JSON is source of truth | Accepted |
| [0010](0010-vlm-baseline-runner.md) | VLM baseline from day one as a decision gate | Accepted |
| [0011](0011-application-stack.md) | FastAPI + Postgres + Redis/arq + Next.js, async only | Accepted |

## The two that would change the project

- **ADR-0007** is driven by a measurement: `surya-ocr` forces `pillow==10.4.0`, which has
  **24 known CVEs**, onto the path that decodes hostile uploads. That single fact sets the
  container topology.
- **ADR-0010** exists because surya already claims **74.6% on Amharic**. The VLM baseline is
  a gate that can conclude the pipeline is not worth building — and is designed to be able
  to say so.
