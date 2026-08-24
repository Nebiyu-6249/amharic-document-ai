"""A general-purpose vision-language model as a baseline (ADR-0010, provider per Q-3).

**This baseline exports personal data and must not be run casually.**

Unlike the text post-correction path, this sends the *page image* to a third-party
provider. C-41 redaction operates on transcribed text and cannot redact a photograph of
a student's exam paper: the name is pixels. Per Q-3 we assume the provider retains what
it receives, so every call is an irreversible disclosure of A-01 (threat T-26).

Therefore this runner refuses any sample that is not explicitly cleared for it. A sample
is cleared only when it is synthetic, or carries research consent from a non-minor
subject -- the same rule the database enforces for training sets (Q-2). The check lives
here rather than in the caller because "remember not to point this at real data" is not
a control.
"""

from __future__ import annotations

import base64
import json
from typing import Final

from adai.eval.types import Corpus, EvalSample, SystemOutput

#: Corpora that may be sent to a third-party provider without a per-sample consent check.
_ALWAYS_CLEARED: Final[frozenset[Corpus]] = frozenset({Corpus.SYNTHETIC})

INSTRUCTION: Final[str] = (
    "Transcribe the Amharic (Ethiopic script) text in this document image. "
    'Return ONLY a JSON object of the form {"text": string}. '
    "Preserve line breaks. Do not translate, summarise, correct or add anything."
)


class SampleNotClearedForEgressError(RuntimeError):
    """Refusing to send a sample containing real personal data to a third party."""


class OpenAIVLMBaseline:
    """Baseline runner for an OpenAI vision model.

    The API key is read from settings (server-side only, Q-3) and never logged.
    """

    name = "openai-vlm"

    def __init__(self, *, model: str, allow_real_data: bool = False) -> None:
        from adai.config import get_settings

        settings = get_settings()
        if settings.openai_api_key is None:
            raise RuntimeError(
                "ADAI_OPENAI_API_KEY is not set; the VLM baseline cannot run. "
                "The key is server-side only and must never reach a client bundle."
            )
        self.model = model
        self._api_key = settings.openai_api_key
        #: Must be set deliberately, per run, by a human who has read the consent rules.
        self.allow_real_data = allow_real_data

    def _assert_cleared(self, sample: EvalSample) -> None:
        if sample.corpus in _ALWAYS_CLEARED:
            return
        if not self.allow_real_data:
            raise SampleNotClearedForEgressError(
                f"sample {sample.id!r} (corpus={sample.corpus}) is not synthetic, and "
                "allow_real_data was not set.\n"
                "\n"
                "Sending it transmits a document image to a third-party provider that "
                "is assumed to retain it (threat T-26). Redaction cannot help: the "
                "personal data is pixels, not text.\n"
                "\n"
                "Only pass allow_real_data=True for samples carrying research consent "
                "from a non-minor subject, and record that decision."
            )

    def transcribe(self, sample: EvalSample) -> SystemOutput:
        self._assert_cleared(sample)
        try:  # pragma: no cover - requires network and a key
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover
            return SystemOutput(text="", error=f"openai package not installed: {exc}")

        try:  # pragma: no cover
            encoded = base64.b64encode(sample.image_path.read_bytes()).decode("ascii")
            client = OpenAI(api_key=self._api_key.get_secret_value())
            response = client.chat.completions.create(
                model=self.model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": INSTRUCTION},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{encoded}"},
                            }
                        ],
                    },
                ],
            )
            payload = json.loads(response.choices[0].message.content or "{}")
        except Exception as exc:
            return SystemOutput(text="", error=f"{type(exc).__name__}: {exc}")

        return SystemOutput(text=str(payload.get("text", "")))
