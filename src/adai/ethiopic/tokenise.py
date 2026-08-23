"""Word tokenisation for Ethiopic text (ADR-0006).

"Word" has no single definition in this script. Classical Ge'ez separates words with
U+1361 ETHIOPIC WORDSPACE; modern Amharic uses U+0020 and treats the wordspace as
archaic or decorative. Real pages mix both.

Splitting on whitespace alone turns a whole line of classical text into one token, so a
near-perfect transcription scores WER near 100%. Splitting on the wordspace alone fails
on modern text. We split on either, and report WER **per corpus** so the two
conventions are never averaged into one meaningless number.
"""

from __future__ import annotations

import re
from typing import Final

from adai.ethiopic.inventory import WORDSPACE

#: Space, wordspace, and any other Unicode whitespace, collapsed.
WORD_SEPARATOR: Final[re.Pattern[str]] = re.compile(rf"[\s{WORDSPACE}]+")


def split_words(text: str) -> list[str]:
    """Split ``text`` into words on whitespace or ETHIOPIC WORDSPACE.

    Empty tokens are dropped, so leading/trailing/repeated separators do not create
    phantom words that would distort WER.
    """
    return [tok for tok in WORD_SEPARATOR.split(text.strip()) if tok]
