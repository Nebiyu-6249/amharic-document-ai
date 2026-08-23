"""Evaluation metrics. Every metric the project is required to report.

Reporting rule (ADR-0006), enforced by :class:`EvalReport`: raw CER and
normalisation-aware CER are always reported **together**. Reporting only the
normalised figure flatters the model by hiding real errors behind the homophone fold;
reporting only the raw figure penalises it for annotator disagreement a human reader
would not notice. Neither alone is honest.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from rapidfuzz.distance import Levenshtein

from adai.ethiopic.normalise import normalise_for_metrics, to_nfc
from adai.ethiopic.tokenise import split_words


def _rate(distance: int, reference_length: int) -> float:
    """Error rate guarding the empty-reference case.

    An empty reference with a non-empty hypothesis is total error (1.0), not a division
    by zero and not a free 0.0. Both of those would quietly flatter a broken model.
    """
    if reference_length == 0:
        return 0.0 if distance == 0 else 1.0
    return distance / reference_length


def character_error_rate(reference: str, hypothesis: str) -> float:
    """Raw CER: Levenshtein distance over characters, divided by reference length.

    NFC-normalised on both sides so an encoding-form difference is never scored as a
    recognition error.
    """
    ref, hyp = to_nfc(reference), to_nfc(hypothesis)
    return _rate(Levenshtein.distance(ref, hyp), len(ref))


#: Short alias; the long name is the canonical one.
cer = character_error_rate


def normalisation_aware_cer(reference: str, hypothesis: str) -> float:
    """CER after folding Ethiopic homophone families (ADR-0006).

    This is the figure that reflects what the model actually got *wrong*, as opposed to
    where it picked a different-but-equivalent glyph. Always report it alongside raw CER.
    """
    ref = normalise_for_metrics(reference)
    hyp = normalise_for_metrics(hypothesis)
    return _rate(Levenshtein.distance(ref, hyp), len(ref))


def wer(reference: str, hypothesis: str) -> float:
    """Word error rate, splitting on whitespace **or** ETHIOPIC WORDSPACE.

    See :mod:`adai.ethiopic.tokenise` for why the separator set matters so much here.
    Report per corpus; pooling classical and modern text produces a meaningless number.
    """
    ref_words = split_words(to_nfc(reference))
    hyp_words = split_words(to_nfc(hypothesis))
    return _rate(Levenshtein.distance(ref_words, hyp_words), len(ref_words))


def normalised_edit_distance(reference: str, hypothesis: str) -> float:
    """NED: edit distance normalised by the longer string. Always in [0, 1]."""
    ref, hyp = to_nfc(reference), to_nfc(hypothesis)
    longest = max(len(ref), len(hyp))
    if longest == 0:
        return 0.0
    return Levenshtein.distance(ref, hyp) / longest


def kendall_tau(reference_order: Sequence[int], predicted_order: Sequence[int]) -> float:
    """Kendall's tau-a between two orderings of the same items.

    This is the reading-order metric. Accuracy is the wrong tool: a page whose columns
    are transposed can have perfect per-character recognition and be useless to read,
    and accuracy would not show it. Tau ranges from 1.0 (identical order) through 0.0
    (uncorrelated) to -1.0 (exactly reversed).
    """
    if len(reference_order) != len(predicted_order):
        raise ValueError("orderings must cover the same number of items")
    n = len(reference_order)
    if n < 2:
        return 1.0

    rank = {item: i for i, item in enumerate(predicted_order)}
    if len(rank) != n:
        raise ValueError("predicted order contains duplicate items")
    try:
        predicted_ranks = [rank[item] for item in reference_order]
    except KeyError as exc:  # pragma: no cover - defensive
        raise ValueError(f"item {exc.args[0]!r} missing from predicted order") from exc

    concordant = discordant = 0
    for i in range(n):
        for j in range(i + 1, n):
            delta = predicted_ranks[i] - predicted_ranks[j]
            if delta < 0:
                concordant += 1
            elif delta > 0:
                discordant += 1
    total_pairs = n * (n - 1) // 2
    return (concordant - discordant) / total_pairs


def field_f1(reference: dict[str, str], predicted: dict[str, str]) -> tuple[float, float, float]:
    """End-to-end field-level precision, recall and F1 on exact value match.

    A field counts as correct only when the key exists in both and the values match
    after metric normalisation.
    """
    if not reference and not predicted:
        return 1.0, 1.0, 1.0
    correct = sum(
        1
        for key, value in predicted.items()
        if key in reference
        and normalise_for_metrics(value) == normalise_for_metrics(reference[key])
    )
    precision = correct / len(predicted) if predicted else 0.0
    recall = correct / len(reference) if reference else 0.0
    if precision + recall == 0:
        return precision, recall, 0.0
    return precision, recall, 2 * precision * recall / (precision + recall)


def _iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    """Intersection over union for two (x0, y0, x1, y1) boxes."""
    ix0, iy0 = max(a[0], b[0]), max(a[1], b[1])
    ix1, iy1 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0)
    if inter <= 0:
        return 0.0
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def layout_map(
    reference: Sequence[tuple[str, tuple[float, float, float, float]]],
    predicted: Sequence[tuple[str, tuple[float, float, float, float], float]],
    iou_threshold: float = 0.5,
) -> dict[str, float]:
    """Layout mAP by region class, at a single IoU threshold.

    ``reference`` is (class, box); ``predicted`` is (class, box, score). Returns average
    precision per class plus a ``"mAP"`` key holding the unweighted mean across classes
    that appear in the reference.
    """
    classes = {cls for cls, _ in reference}
    results: dict[str, float] = {}

    for cls in sorted(classes):
        gt = [box for c, box in reference if c == cls]
        preds = sorted(
            ((box, score) for c, box, score in predicted if c == cls),
            key=lambda item: item[1],
            reverse=True,
        )
        if not gt:
            continue
        matched: set[int] = set()
        tp_fp: list[int] = []
        for box, _score in preds:
            best_iou, best_idx = 0.0, -1
            for idx, gt_box in enumerate(gt):
                if idx in matched:
                    continue
                overlap = _iou(box, gt_box)
                if overlap > best_iou:
                    best_iou, best_idx = overlap, idx
            if best_iou >= iou_threshold and best_idx >= 0:
                matched.add(best_idx)
                tp_fp.append(1)
            else:
                tp_fp.append(0)

        # 11-point-free AP: area under the precision-recall curve by summation.
        running_tp = 0
        ap = 0.0
        for i, is_tp in enumerate(tp_fp, start=1):
            if is_tp:
                running_tp += 1
                ap += running_tp / i
        results[cls] = ap / len(gt)

    results["mAP"] = sum(results.values()) / len(results) if results else 0.0
    return results


@dataclass(frozen=True)
class EvalReport:
    """The mandatory metric set for one evaluation split.

    Constructing this type is the only supported way to report results, which is how
    the "always report raw and normalised CER together" rule is enforced structurally
    rather than by convention.
    """

    split: str
    corpus: str
    n_samples: int
    cer: float
    normalisation_aware_cer: float
    wer: float
    ned: float
    reading_order_tau: float | None = None
    layout_map: dict[str, float] = field(default_factory=dict)
    field_f1: float | None = None
    notes: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "split": self.split,
            "corpus": self.corpus,
            "n_samples": self.n_samples,
            "cer": round(self.cer, 5),
            "normalisation_aware_cer": round(self.normalisation_aware_cer, 5),
            "wer": round(self.wer, 5),
            "ned": round(self.ned, 5),
            "reading_order_tau": (
                None if self.reading_order_tau is None else round(self.reading_order_tau, 5)
            ),
            "layout_map": {k: round(v, 5) for k, v in self.layout_map.items()},
            "field_f1": None if self.field_f1 is None else round(self.field_f1, 5),
            "notes": self.notes,
        }
