---
name: ocr-eval
description: >
  How to evaluate recognition quality in this project - the mandatory metric set, the
  three required splits, how to run the harness and the VLM baselines, and the reporting
  rules that keep results honest. Use this skill whenever you measure, benchmark,
  compare or report OCR/recognition/layout/reading-order quality, add a metric, run
  adai-eval, build a train/test split, write up results, or answer "how well does it
  work" - including when the request just says "test the model" or "see if it's any
  good". Several ways of reporting these numbers are misleading rather than merely
  imprecise, so check the reporting rules here before quoting any figure.
---

# Evaluating recognition quality

The point of this harness is to make dishonest reporting harder than honest reporting.
Most of the rules below exist because a plausible-looking shortcut produces a number
that is wrong in a flattering direction.

## Run it

```bash
adai-eval --list-systems                          # what can be measured
adai-eval --system pipeline --split iid           # our pipeline
adai-eval --system surya    --split unseen_capture   # off-the-shelf baseline
adai-eval --system pipeline --split iid --json    # machine-readable
```

Exit codes carry meaning: **0** a real result, **1** the run contained stub stages and
is not a result, **2** it refused to run (no corpus, or an empty split).

Programmatically:

```python
from adai.eval import evaluate, format_report, build_splits
run = evaluate(system, splits.iid, split="iid")
print(format_report(run))
```

Any object with `name` and `transcribe(sample) -> SystemOutput` is measurable, so our
pipeline and a frontier VLM go through identical code on identical samples. That
identity is the whole point — a baseline measured differently is not a baseline.

## The mandatory metric set

Report all of these. They fail differently, and a system can look fine on one while
being useless.

| Metric | What it catches | Notes |
|---|---|---|
| **CER** | character recognition | raw; penalises homophone choice |
| **Normalisation-aware CER** | recognition minus orthographic disagreement | uses the four fold families |
| **WER** | word-level errors | splits on space **and** `፡` |
| **NED** | length-normalised distance | always in [0,1] |
| **Layout mAP** | region detection, per class | needs region ground truth |
| **Reading-order Kendall's tau** | serialisation order | **not** accuracy — see below |
| **Field-level F1** | end-to-end usefulness | exact match after normalisation |

### Why tau and not accuracy for reading order

A page whose two columns are transposed can have perfect per-character recognition and
be unreadable. Accuracy cannot see that; it is a property of the *ordering*, and tau
measures orderings. Tau runs 1.0 (identical) → 0.0 (uncorrelated) → −1.0 (reversed).

## Reporting rules

These are not style preferences. Each one prevents a specific way of being wrong.

### 1. Always publish both CER figures together

Raw CER punishes the model for choosing ሰ where the reference has ሠ — a distinction a
human reader does not notice. Normalisation-aware CER absorbs that, but also hides
genuine errors. Publishing only the flattering one is the single easiest way to
misrepresent this project's results. `EvalReport` carries both fields so the omission
has to be deliberate.

### 2. Never pool WER across corpora

Classical Ge'ez delimits words with `፡`; modern Amharic uses spaces. A pooled WER
describes neither convention. `evaluate()` groups by corpus automatically — keep it
that way when you write results up.

### 3. A stubbed run is not a result

Layout, line segmentation and recognition are currently stubs (ADR-0005), so the
pipeline scores CER ≈ 1.0 on everything. That is a measurement of the stub. The harness
sets `contains_stub_stages`, stamps a warning into `notes`, prints it in the report and
returns exit 1. Do not quote such a run, and do not strip the warning.

### 4. Never report metrics over an empty corpus or split

Zero samples score 0.0 on every metric, which reads exactly like a perfect system. The
CLI refuses with exit 2 rather than printing zeros, and `Splits.gaps` names any split
with no data.

### 5. Errored samples are scored, not skipped

A sample the system failed on counts as total error (1.0). Skipping failures quietly
improves the mean, which rewards a brittle system.

## The three splits

```python
from adai.eval import build_splits
splits = build_splits(samples)
print(splits.gaps)   # any split with no data
```

| Split | Question it answers |
|---|---|
| **iid** | Can it do this at all, on data like its training data? |
| **unseen_writer** | Does it generalise across handwriting, or has it memorised writers? |
| **unseen_capture** | Does it survive a real phone photo? |

**Writers are held out whole.** Splitting one writer's samples across train and test is
the classic leak that makes a memorising model look like a generalising one, and
`build_splits` will not do it.

**unseen_capture is the split that matters for the product claim, and no public dataset
provides it.** Fidel and HHD-Ethiopic are both pre-cropped line images — neither
contains warped, shadowed or ruled-paper captures of full pages. That data has to be
collected with consent. `build_splits` returns an empty `unseen_capture` rather than
substituting IID data: an empty split is a visible gap, a substituted one is a false
result.

## Baselines

`docs/adr/0010-vlm-baseline-runner.md` treats the baseline as a decision gate, not a
formality: surya's own table reports Amharic at **74.6%**, so "an off-the-shelf VLM may
already be good enough" is a live possibility. If the baseline wins, say so.

| System | Constraint |
|---|---|
| `pipeline` | Currently stubbed |
| `surya` | Quarantined container only — it forces pillow 10.4.0, 24 known CVEs (ADR-0007) |
| `openai-vlm` | **Exports the page image to a third party.** Refuses non-synthetic samples unless `allow_real_data=True` |

The VLM baseline's consent gate is not bureaucracy. Redaction (C-41) works on
transcribed text; it cannot redact a photograph, because there the student's name is
pixels. Every call is an irreversible disclosure (threat T-26).

## Further reading

- `references/metrics.md` — exact definitions, edge-case behaviour, and worked examples.
- `docs/adr/0006-...` — why both CER figures, and the tokenisation rule.
- `docs/adr/0010-...` — the baseline as a decision gate.
- `.claude/skills/ethiopic-script/SKILL.md` — the normalisation the metrics depend on.
