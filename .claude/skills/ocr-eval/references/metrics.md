# Metric definitions and edge cases

Implementations live in `src/adai/eval/metrics.py`. This file records the decisions that
are not obvious from the signatures.

## Contents

- [Edge-case behaviour](#edge-case-behaviour)
- [Worked examples](#worked-examples)
- [Layout mAP](#layout-map)
- [Adding a metric](#adding-a-metric)

## Edge-case behaviour

| Situation | Result | Why |
|---|---|---|
| empty reference, empty hypothesis | 0.0 | nothing to get wrong |
| empty reference, non-empty hypothesis | **1.0** | total error — not a division by zero, and not a free 0.0 |
| empty hypothesis, non-empty reference | 1.0 | the system produced nothing |
| NED with both empty | 0.0 | |
| tau with fewer than 2 items | 1.0 | ordering is trivially correct |
| tau with duplicate ids | `ValueError` | a malformed ordering is a bug, not a score |
| tau with mismatched lengths | `ValueError` | comparing different item sets is meaningless |
| field F1 with both dicts empty | (1.0, 1.0, 1.0) | vacuously correct |

The empty-reference case matters more than it looks. Returning 0.0 there would let a
system that outputs garbage on blank pages score perfectly on them.

## Worked examples

### Homophone substitution — the two CER figures diverge

```python
reference, hypothesis = "ሰላም ለዓለም", "ሠላም ለዓለም"     # ሰ -> ሠ, same sound
character_error_rate(reference, hypothesis)        # 0.125
normalisation_aware_cer(reference, hypothesis)     # 0.0
wer(reference, hypothesis)                         # 0.5  (one of two words differs)
```

The model read the glyph correctly and chose an interchangeable variant. Raw CER calls
that an error; normalisation-aware CER does not. Report both.

### Classical text — why the separator matters

```python
reference = "ወጽራኅየኒ፡ቦአ፡ቅድሜሁ"        # three ፡-delimited words
wer(reference, "ወጽራኅየኒ፡ቦአ፡ቅድሜህ")   # 0.333 — one word wrong

# If WER split on whitespace only, the whole line would be one token
# and this same near-perfect transcription would score 1.0.
```

### Reading order — transposed columns

```python
kendall_tau([0, 1, 2, 3], [0, 1, 2, 3])   #  1.0  identical
kendall_tau([0, 1, 2, 3], [1, 0, 2, 3])   #  0.667 one adjacent swap
kendall_tau([0, 1, 2, 3], [2, 3, 0, 1])   # -0.333 columns transposed
kendall_tau([0, 1, 2, 3], [3, 2, 1, 0])   # -1.0  fully reversed
```

Per-character accuracy would be 100% in every one of these cases.

## Layout mAP

`layout_map(reference, predicted, iou_threshold=0.5)` takes `(class, bbox)` for the
reference and `(class, bbox, score)` for predictions, returns average precision per
class plus an unweighted `"mAP"` across classes present in the reference.

Boxes are `(x0, y0, x1, y1)` with origin top-left. Predictions are matched greedily by
descending score, and each ground-truth box can be matched once — so duplicate
detections of the same region count as false positives, which is the behaviour you want.

Only classes that appear in the reference contribute. A class the system hallucinates
that is absent from the ground truth lowers precision for its own class rather than
silently vanishing.

## Adding a metric

1. Put it in `src/adai/eval/metrics.py`, with the empty-input behaviour decided
   deliberately and documented in the table above.
2. Add a field to `EvalReport` and to `as_dict()`, so it reaches the JSON output.
3. Add a column to `format_report` if it belongs in the at-a-glance table.
4. Write a test that fails if the metric silently returns 0.0 on empty input — that is
   the failure mode that makes a broken system look perfect.
