"""``adai-eval`` — command-line entry point for the evaluation harness.

Usage:
    adai-eval --system pipeline --split iid
    adai-eval --system surya    --split unseen_capture
    adai-eval --list-systems

Every path through this CLI ends in either a real measurement or an explicit,
actionable refusal. There is no mode in which it prints plausible numbers it did not
measure.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from adai.eval.harness import evaluate, format_report
from adai.eval.splits import build_splits
from adai.eval.types import RecognitionSystem

SPLITS = ("iid", "unseen_writer", "unseen_capture")


def _load_system(name: str) -> RecognitionSystem:
    if name == "pipeline":
        from adai.eval.baselines.pipeline_system import PipelineSystem

        return PipelineSystem()
    if name == "surya":
        from adai.eval.baselines.surya_baseline import SuryaBaseline

        return SuryaBaseline()
    if name == "openai-vlm":
        from adai.eval.baselines.openai_vlm import OpenAIVLMBaseline

        return OpenAIVLMBaseline(model="gpt-4o")
    raise SystemExit(f"unknown system: {name!r}. Try --list-systems.")


def _load_samples() -> list[object]:
    """Load the evaluation corpus.

    Raises rather than returning an empty list: an empty corpus would produce a clean
    report full of zeros, which is indistinguishable from a perfect score.
    """
    from adai.data.fidel import FidelNotAvailableError, is_available, load_split

    if not is_available():
        raise FidelNotAvailableError(
            "No evaluation corpus is available.\n"
            "\n"
            "The Fidel dataset is the primary evaluation corpus (ADR-0008) and it has "
            "not been obtained: huggingface.co is blocked by the egress policy, so the "
            "schema was never observed and no loader may be written against a guess.\n"
            "\n"
            "Refusing to run rather than reporting zeros over an empty corpus, which "
            "would look like a perfect score.\n"
            "\n"
            "See docs/STATUS.md section 6 for the two ways to unblock this."
        )
    return list(load_split("test"))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="adai-eval", description=__doc__)
    parser.add_argument("--system", default="pipeline", help="system under test")
    parser.add_argument("--split", default="iid", choices=SPLITS)
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument(
        "--list-systems", action="store_true", help="list available systems and exit"
    )
    args = parser.parse_args(argv)

    if args.list_systems:
        print("pipeline    our five-stage pipeline (currently stubbed - see ADR-0005)")
        print("surya       off-the-shelf baseline; quarantined container only (ADR-0007)")
        print("openai-vlm  frontier VLM baseline; exports images to a third party (T-26)")
        return 0

    try:
        samples = _load_samples()
    except NotImplementedError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    system = _load_system(args.system)
    splits = build_splits(samples)  # type: ignore[arg-type]
    selected = splits.as_dict()[args.split]

    if not selected:
        print(
            f"split {args.split!r} is empty.\n"
            "Not reporting metrics over zero samples - an empty split scores 0.0 on "
            "everything, which reads as perfect.\n"
            f"Splits with no data: {', '.join(splits.gaps)}",
            file=sys.stderr,
        )
        return 2

    run = evaluate(system, selected, split=args.split)
    print(json.dumps(run.as_dict(), indent=2) if args.json else format_report(run))
    # A stubbed run is not a result, so it is not a success either.
    return 1 if run.contains_stub_stages else 0


if __name__ == "__main__":
    raise SystemExit(main())
