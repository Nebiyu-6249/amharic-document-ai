"""The three mandatory evaluation splits.

They answer three different questions, and only the third one speaks to the product
claim:

* **IID** — can the model do this at all, on data like its training data?
* **unseen-writer** — does it generalise across handwriting, or has it memorised writers?
* **unseen-capture-condition** — does it survive a real phone photo?

The third is the one that matters and the one no public dataset provides. Fidel and
HHD-Ethiopic are both pre-cropped line images; neither contains warped, shadowed or
ruled-paper captures of full pages. That split has to be collected, with consent
(docs/STATUS.md). :func:`build_splits` will produce an empty unseen-capture split rather
than silently substituting IID data for it -- an empty split is a visible gap, a
substituted one is a false result.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from adai.eval.types import CaptureCondition, EvalSample


@dataclass(frozen=True)
class Splits:
    iid: tuple[EvalSample, ...]
    unseen_writer: tuple[EvalSample, ...]
    unseen_capture: tuple[EvalSample, ...]

    def as_dict(self) -> dict[str, tuple[EvalSample, ...]]:
        return {
            "iid": self.iid,
            "unseen_writer": self.unseen_writer,
            "unseen_capture": self.unseen_capture,
        }

    @property
    def gaps(self) -> list[str]:
        """Splits with no samples. Reported loudly rather than quietly skipped."""
        return [name for name, samples in self.as_dict().items() if not samples]


def _stable_bucket(value: str, buckets: int) -> int:
    """Deterministic hash bucket.

    Deliberately not Python's ``hash()``: that is salted per process, so splits would
    silently differ between runs and results would not be comparable.
    """
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % buckets


def build_splits(
    samples: Iterable[EvalSample],
    *,
    holdout_writer_fraction: float = 0.2,
    training_conditions: Sequence[CaptureCondition] = (
        CaptureCondition.SCAN,
        CaptureCondition.PHONE_FLAT,
    ),
) -> Splits:
    """Partition samples into the three splits.

    A writer is held out whole -- every one of their samples goes to unseen_writer, or
    none does. Splitting a writer's samples across both sides is the classic leak that
    makes a memorising model look like a generalising one.
    """
    materialised = list(samples)
    holdout_buckets = max(1, round(holdout_writer_fraction * 10))

    held_out_writers = {
        sample.writer_id
        for sample in materialised
        if sample.writer_id and _stable_bucket(sample.writer_id, 10) < holdout_buckets
    }
    training_set = set(training_conditions)

    iid: list[EvalSample] = []
    unseen_writer: list[EvalSample] = []
    unseen_capture: list[EvalSample] = []

    for sample in materialised:
        # Capture condition takes precedence: a warped photo from a known writer still
        # tests the capture question, which is the harder and more product-relevant one.
        if sample.capture_condition not in training_set:
            unseen_capture.append(sample)
        elif sample.writer_id in held_out_writers:
            unseen_writer.append(sample)
        else:
            iid.append(sample)

    return Splits(
        iid=tuple(iid), unseen_writer=tuple(unseen_writer), unseen_capture=tuple(unseen_capture)
    )
