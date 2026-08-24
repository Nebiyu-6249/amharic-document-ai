"""Evaluation harness."""

from adai.eval.harness import RunResult, SampleResult, evaluate, format_report
from adai.eval.metrics import (
    EvalReport,
    cer,
    character_error_rate,
    field_f1,
    kendall_tau,
    layout_map,
    normalisation_aware_cer,
    normalised_edit_distance,
    wer,
)
from adai.eval.splits import Splits, build_splits
from adai.eval.types import CaptureCondition, Corpus, EvalSample, SystemOutput

__all__ = [
    "CaptureCondition",
    "Corpus",
    "EvalReport",
    "EvalSample",
    "RunResult",
    "SampleResult",
    "Splits",
    "SystemOutput",
    "build_splits",
    "cer",
    "character_error_rate",
    "evaluate",
    "field_f1",
    "format_report",
    "kendall_tau",
    "layout_map",
    "normalisation_aware_cer",
    "normalised_edit_distance",
    "wer",
]
