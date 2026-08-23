"""PII redaction for stored transcriptions (control C-41, threats T-07/T-20/T-26).

**Read this before trusting it.**

Per Q-3 we assume the LLM provider retains what we send, so redaction must run *before*
anything crosses TB-06. This module implements the part of that which can be done
deterministically and correctly:

* email addresses
* Ethiopian and international phone numbers
* long digit runs (ID numbers, account numbers)
* dates in common numeric formats

**What it deliberately does NOT do: detect person names.** Amharic personal names are
ordinary Ethiopic words with no case marking, no honorific requirement and no reliable
surface pattern. A regex cannot find them, and a regex that pretended to would create
exactly the false sense of safety this project is supposed to avoid: a transcription
would be marked "redacted" while a student's name sat in plain text.

Name redaction needs a trained Amharic NER model. That is not available here and is
recorded as an open gap in docs/SECURITY.md and docs/STATUS.md. Until it exists,
:func:`redact` returns ``names_detected=False`` and callers that require full redaction
before egress must consult :attr:`RedactionResult.is_complete`, which is always False.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Final

EMAIL_TOKEN: Final[str] = "[EMAIL]"  # noqa: S105 - a redaction placeholder, not a credential
PHONE_TOKEN: Final[str] = "[PHONE]"  # noqa: S105 - a redaction placeholder, not a credential
NUMBER_ID_TOKEN: Final[str] = "[ID]"  # noqa: S105 - a redaction placeholder, not a credential
DATE_TOKEN: Final[str] = "[DATE]"  # noqa: S105 - a redaction placeholder, not a credential

_EMAIL = re.compile(r"\b[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
# +251 9xx xxx xxx / 09xx xxx xxx / generic international.
_PHONE = re.compile(r"(?:\+251[\s-]?|\b0)\d{2}[\s-]?\d{3}[\s-]?\d{3,4}\b|\+\d{10,15}\b")
# Long digit runs: national IDs, account and roll numbers. Deliberately >= 6 so that
# marks out of 100 and two-digit ages are not destroyed.
_LONG_DIGITS = re.compile(r"\b\d{6,}\b")
_DATE = re.compile(r"\b\d{1,4}[/-]\d{1,2}[/-]\d{1,4}\b")


@dataclass(frozen=True)
class RedactionResult:
    text: str
    counts: dict[str, int] = field(default_factory=dict)
    #: Always False while name detection is unimplemented. See the module docstring.
    names_detected: bool = False

    @property
    def is_complete(self) -> bool:
        """Whether redaction can be considered exhaustive.

        Hard-coded False: without name detection no transcription of a school document
        can honestly be called fully de-identified.
        """
        return False

    @property
    def redacted_anything(self) -> bool:
        return any(self.counts.values())


def redact(text: str) -> RedactionResult:
    """Apply deterministic redactions. See the module docstring for the known gap."""
    counts: dict[str, int] = {}

    def _sub(pattern: re.Pattern[str], token: str, label: str, value: str) -> str:
        replaced, n = pattern.subn(token, value)
        if n:
            counts[label] = counts.get(label, 0) + n
        return replaced

    out = text
    out = _sub(_EMAIL, EMAIL_TOKEN, "email", out)
    out = _sub(_PHONE, PHONE_TOKEN, "phone", out)
    out = _sub(_DATE, DATE_TOKEN, "date", out)
    out = _sub(_LONG_DIGITS, NUMBER_ID_TOKEN, "long_digits", out)
    return RedactionResult(text=out, counts=counts)
