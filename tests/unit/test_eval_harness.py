"""The evaluation harness, splits and CLI."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image

from adai.eval.harness import evaluate, format_report
from adai.eval.splits import build_splits
from adai.eval.types import CaptureCondition, Corpus, EvalSample, SystemOutput


def _sample(
    sid: str,
    text: str = "ሰላም ለዓለም",
    corpus: Corpus = Corpus.FIDEL,
    writer: str | None = None,
    condition: CaptureCondition = CaptureCondition.SCAN,
) -> EvalSample:
    return EvalSample(
        id=sid,
        image_path=Path("/nonexistent.jpg"),
        reference_text=text,
        corpus=corpus,
        writer_id=writer,
        capture_condition=condition,
    )


class _Oracle:
    name = "oracle"

    def transcribe(self, sample: EvalSample) -> SystemOutput:
        return SystemOutput(text=sample.reference_text)


class _HomophoneSwap:
    name = "homophone"

    def transcribe(self, sample: EvalSample) -> SystemOutput:
        return SystemOutput(text=sample.reference_text.replace("ሰ", "ሠ"))


class _Silent:
    name = "silent"

    def transcribe(self, sample: EvalSample) -> SystemOutput:
        return SystemOutput(text="")


class _Stubbed:
    name = "stubbed"

    def transcribe(self, sample: EvalSample) -> SystemOutput:
        return SystemOutput(text="", contains_stub_stages=True)


class _Broken:
    name = "broken"

    def transcribe(self, sample: EvalSample) -> SystemOutput:
        return SystemOutput(text="", error="decoder exploded")


# --- harness ------------------------------------------------------------------------


def test_perfect_system_scores_zero_error() -> None:
    run = evaluate(_Oracle(), [_sample("a")], split="iid")
    report = run.reports[0]
    assert report.cer == 0.0
    assert report.normalisation_aware_cer == 0.0
    assert report.wer == 0.0


def test_homophone_only_difference_separates_the_two_cer_figures() -> None:
    """The ADR-0006 claim, asserted end to end through the harness."""
    run = evaluate(_HomophoneSwap(), [_sample("a")], split="iid")
    report = run.reports[0]
    assert report.cer > 0.0, "raw CER should penalise the substitution"
    assert report.normalisation_aware_cer == 0.0, "the fold should absorb it"


def test_empty_output_is_total_error_not_a_free_pass() -> None:
    run = evaluate(_Silent(), [_sample("a")], split="iid")
    assert run.reports[0].cer == 1.0


def test_results_are_reported_per_corpus_never_pooled() -> None:
    """Classical and modern text use different word separators; a pooled WER is
    meaningless (ADR-0006)."""
    samples = [
        _sample("a", "ሰላም ለዓለም", Corpus.FIDEL),
        _sample("b", "ወጽራኅየኒ፡ቦአ", Corpus.HHD_ETHIOPIC),
    ]
    run = evaluate(_Oracle(), samples, split="iid")
    assert {r.corpus for r in run.reports} == {"fidel", "hhd_ethiopic"}
    assert all(r.n_samples == 1 for r in run.reports)


def test_a_failing_sample_is_scored_not_skipped() -> None:
    """Skipping errors would quietly improve the average."""
    run = evaluate(_Broken(), [_sample("a"), _sample("b")], split="iid")
    assert run.failed_samples == 2
    assert run.reports[0].cer == 1.0


def test_stubbed_run_is_flagged_everywhere() -> None:
    """A stubbed run is not a result and must be impossible to quote as one."""
    run = evaluate(_Stubbed(), [_sample("a")], split="iid")
    assert run.contains_stub_stages is True
    assert "STUB" in run.reports[0].notes.upper()
    assert "STUB" in format_report(run).upper()


def test_report_always_prints_both_cer_columns() -> None:
    text = format_report(evaluate(_Oracle(), [_sample("a")], split="iid"))
    assert "CER" in text
    assert "nCER" in text


def test_reading_order_tau_is_computed_when_ground_truth_exists() -> None:
    class _Reverser:
        name = "reverser"

        def transcribe(self, sample: EvalSample) -> SystemOutput:
            return SystemOutput(
                text=sample.reference_text, predicted_order=tuple(reversed(sample.reference_order))
            )

    sample = EvalSample(
        id="a",
        image_path=Path("/x.jpg"),
        reference_text="t",
        corpus=Corpus.FIDEL,
        reference_order=(0, 1, 2, 3),
    )
    run = evaluate(_Reverser(), [sample], split="iid")
    assert run.reports[0].reading_order_tau == -1.0


# --- splits -------------------------------------------------------------------------


def test_a_writer_is_never_split_across_iid_and_holdout() -> None:
    """The classic leak that makes a memorising model look like it generalises."""
    samples = [_sample(f"s{i}", writer=f"w{i % 40}") for i in range(400)]
    splits = build_splits(samples)
    iid_writers = {s.writer_id for s in splits.iid}
    holdout_writers = {s.writer_id for s in splits.unseen_writer}
    assert not (iid_writers & holdout_writers)
    assert holdout_writers, "with 40 writers some should be held out"


def test_splits_are_deterministic_across_runs() -> None:
    samples = [_sample(f"s{i}", writer=f"w{i % 30}") for i in range(120)]
    first = {s.id for s in build_splits(samples).unseen_writer}
    second = {s.id for s in build_splits(samples).unseen_writer}
    assert first == second


def test_unseen_capture_condition_takes_precedence() -> None:
    samples = [_sample("a", writer="w1", condition=CaptureCondition.PHONE_WARPED)]
    splits = build_splits(samples)
    assert len(splits.unseen_capture) == 1
    assert not splits.iid


def test_missing_split_is_reported_as_a_gap_not_hidden() -> None:
    """No public dataset provides warped phone captures; that gap must be visible."""
    samples = [_sample(f"s{i}", writer="w1") for i in range(5)]
    splits = build_splits(samples)
    assert "unseen_capture" in splits.gaps


# --- baselines and CLI ----------------------------------------------------------------


def test_pipeline_adapter_propagates_the_stub_marker(tmp_path: Path) -> None:
    from adai.eval.baselines.pipeline_system import PipelineSystem

    image_path = tmp_path / "page.jpg"
    buf = io.BytesIO()
    Image.new("RGB", (60, 40), (240, 240, 235)).save(buf, "JPEG")
    image_path.write_bytes(buf.getvalue())

    output = PipelineSystem().transcribe(
        EvalSample(id="a", image_path=image_path, reference_text="t", corpus=Corpus.FIDEL)
    )
    assert output.contains_stub_stages is True
    assert output.error is None


def test_pipeline_adapter_reports_a_bad_sample_without_crashing() -> None:
    from adai.eval.baselines.pipeline_system import PipelineSystem

    output = PipelineSystem().transcribe(_sample("missing"))
    assert output.error is not None


def test_vlm_baseline_refuses_real_data_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """C-41 cannot redact a photograph: the personal data is pixels (threat T-26)."""
    monkeypatch.setenv("ADAI_OPENAI_API_KEY", "sk-test-not-a-real-key")
    from adai.config import get_settings
    from adai.eval.baselines.openai_vlm import (
        OpenAIVLMBaseline,
        SampleNotClearedForEgressError,
    )

    get_settings.cache_clear()
    try:
        baseline = OpenAIVLMBaseline(model="gpt-4o")
        with pytest.raises(SampleNotClearedForEgressError, match="not synthetic"):
            baseline.transcribe(_sample("a", corpus=Corpus.FIDEL))
    finally:
        get_settings.cache_clear()


def test_surya_baseline_explains_why_it_is_not_installed() -> None:
    from adai.eval.baselines.surya_baseline import SuryaBaseline, SuryaUnavailableError

    with pytest.raises(SuryaUnavailableError, match=r"pillow 10\.4\.0"):
        SuryaBaseline()


def test_cli_lists_systems() -> None:
    from adai.eval.cli import main

    assert main(["--list-systems"]) == 0


def test_cli_refuses_to_run_without_a_corpus(capsys: pytest.CaptureFixture[str]) -> None:
    """An empty corpus would score 0.0 on everything, which reads as perfect."""
    from adai.eval.cli import main

    assert main(["--system", "pipeline", "--split", "iid"]) == 2
    assert "No evaluation corpus is available" in capsys.readouterr().err


def test_declared_console_script_resolves() -> None:
    """Regression: pyproject declared adai-eval before the module existed."""
    import importlib

    module = importlib.import_module("adai.eval.cli")
    assert callable(module.main)
