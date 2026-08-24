"""The evaluation harness.

Runs any :class:`~adai.eval.types.RecognitionSystem` over a split and produces the
mandatory metric set. Two rules are enforced structurally rather than by convention:

1. **Raw and normalisation-aware CER are always reported together** (ADR-0006). Raw CER
   punishes the model for homophone choices a human reader would not notice;
   normalisation-aware CER hides real errors behind the fold. Either alone misleads.
2. **A run containing stub stages is marked and is not a result.** The pipeline
   currently stubs layout, line segmentation and recognition, so it would score CER 1.0
   on everything. Reporting that as a measurement would be worse than reporting nothing.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import dataclass, field

from adai.eval.metrics import (
    EvalReport,
    character_error_rate,
    field_f1,
    kendall_tau,
    layout_map,
    normalisation_aware_cer,
    normalised_edit_distance,
    wer,
)
from adai.eval.types import Corpus, EvalSample, RecognitionSystem, SystemOutput
from adai.logging import get_logger

log = get_logger("adai.eval")


@dataclass(frozen=True)
class SampleResult:
    sample_id: str
    corpus: Corpus
    cer: float
    normalised_cer: float
    wer: float
    ned: float
    tau: float | None = None
    error: str | None = None


@dataclass(frozen=True)
class RunResult:
    """A full evaluation run: per-corpus reports plus the raw per-sample numbers."""

    system: str
    split: str
    reports: tuple[EvalReport, ...]
    samples: tuple[SampleResult, ...] = field(default_factory=tuple)
    contains_stub_stages: bool = False
    failed_samples: int = 0

    def as_dict(self) -> dict[str, object]:
        return {
            "system": self.system,
            "split": self.split,
            "contains_stub_stages": self.contains_stub_stages,
            "failed_samples": self.failed_samples,
            "reports": [report.as_dict() for report in self.reports],
        }


def _mean(values: Sequence[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def evaluate(system: RecognitionSystem, samples: Sequence[EvalSample], *, split: str) -> RunResult:
    """Evaluate one system on one split, reporting per corpus.

    Per corpus, not pooled: WER depends on the word-separator convention, which differs
    between classical and modern text (ADR-0006).
    """
    per_sample: list[SampleResult] = []
    saw_stub = False
    failures = 0

    for sample in samples:
        output: SystemOutput = system.transcribe(sample)
        saw_stub = saw_stub or output.contains_stub_stages
        if output.error:
            failures += 1
            per_sample.append(
                SampleResult(
                    sample_id=sample.id,
                    corpus=sample.corpus,
                    cer=1.0,
                    normalised_cer=1.0,
                    wer=1.0,
                    ned=1.0,
                    error=output.error,
                )
            )
            continue

        tau: float | None = None
        if sample.reference_order and output.predicted_order:
            try:
                tau = kendall_tau(sample.reference_order, output.predicted_order)
            except ValueError as exc:
                # A malformed ordering is a system failure, not a crash of the harness.
                log.warning("tau_skipped", sample=sample.id, reason=str(exc))

        per_sample.append(
            SampleResult(
                sample_id=sample.id,
                corpus=sample.corpus,
                cer=character_error_rate(sample.reference_text, output.text),
                normalised_cer=normalisation_aware_cer(sample.reference_text, output.text),
                wer=wer(sample.reference_text, output.text),
                ned=normalised_edit_distance(sample.reference_text, output.text),
                tau=tau,
            )
        )

    reports: list[EvalReport] = []
    for corpus in sorted({s.corpus for s in samples}):
        subset = [r for r in per_sample if r.corpus == corpus]
        corpus_samples = [s for s in samples if s.corpus == corpus]
        taus = [r.tau for r in subset if r.tau is not None]

        # Layout mAP and field F1 are only meaningful where ground truth exists.
        map_scores: dict[str, float] = {}
        references = [s for s in corpus_samples if s.reference_regions]
        if references:
            merged = layout_map(
                [region for s in references for region in s.reference_regions],
                [region for s in references for region in system.transcribe(s).predicted_regions],
            )
            map_scores = merged

        field_scores = [
            field_f1(s.reference_fields, system.transcribe(s).predicted_fields)[2]
            for s in corpus_samples
            if s.reference_fields
        ]

        notes = ""
        if saw_stub:
            notes = (
                "RUN CONTAINS STUB STAGES - these numbers measure the stub, not a "
                "recogniser. Not a result."
            )

        reports.append(
            EvalReport(
                split=split,
                corpus=str(corpus),
                n_samples=len(subset),
                cer=_mean([r.cer for r in subset]),
                normalisation_aware_cer=_mean([r.normalised_cer for r in subset]),
                wer=_mean([r.wer for r in subset]),
                ned=_mean([r.ned for r in subset]),
                reading_order_tau=_mean(taus) if taus else None,
                layout_map=map_scores,
                field_f1=_mean(field_scores) if field_scores else None,
                notes=notes,
            )
        )

    return RunResult(
        system=system.name,
        split=split,
        reports=tuple(reports),
        samples=tuple(per_sample),
        contains_stub_stages=saw_stub,
        failed_samples=failures,
    )


def format_report(run: RunResult) -> str:
    """Human-readable summary. Always prints both CER figures side by side."""
    lines = [
        f"system: {run.system}    split: {run.split}",
        f"{'corpus':<16}{'n':>6}{'CER':>9}{'nCER':>9}{'WER':>9}{'NED':>9}{'tau':>8}{'mAP':>8}",
        "-" * 74,
    ]
    for report in run.reports:
        tau = "-" if report.reading_order_tau is None else f"{report.reading_order_tau:.3f}"
        m_ap = f"{report.layout_map['mAP']:.3f}" if "mAP" in report.layout_map else "-"
        lines.append(
            f"{report.corpus:<16}{report.n_samples:>6}{report.cer:>9.4f}"
            f"{report.normalisation_aware_cer:>9.4f}{report.wer:>9.4f}"
            f"{report.ned:>9.4f}{tau:>8}{m_ap:>8}"
        )
    if run.failed_samples:
        lines.append(f"\n{run.failed_samples} sample(s) errored and were scored as total error.")
    if run.contains_stub_stages:
        lines.append(
            "\n*** THIS RUN CONTAINS STUB STAGES. The numbers describe the stub, not a\n"
            "    recogniser, and must not be quoted as a result. See docs/STATUS.md. ***"
        )
    return "\n".join(lines)
