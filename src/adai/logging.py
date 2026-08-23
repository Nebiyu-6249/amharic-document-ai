"""Structured logging with mandatory redaction (control C-38).

Security events must be logged; secrets, tokens and document content must never be.
Those two requirements pull in opposite directions, so redaction is applied by a
processor in the pipeline rather than left to each call site to remember.
"""

from __future__ import annotations

import logging
import re
import sys
from collections.abc import MutableMapping
from typing import Any, Final

import structlog

#: Keys whose values are replaced wholesale, whatever they contain.
REDACTED_KEYS: Final[frozenset[str]] = frozenset(
    {
        "password",
        "password_hash",
        "secret",
        "secret_key",
        "token",
        "access_token",
        "refresh_token",
        "reset_token",
        "csrf_token",
        "session_id",
        "authorization",
        "cookie",
        "set_cookie",
        "api_key",
        "openai_api_key",
        "database_url",
        # Document content is personal data (T-19). It never goes to a log.
        "text",
        "markdown",
        "transcription",
        "ocr_text",
        "content",
    }
)

_PLACEHOLDER: Final[str] = "[redacted]"

#: Belt and braces: catch secret-shaped values even under an unexpected key.
_SECRET_SHAPED: Final[re.Pattern[str]] = re.compile(
    r"(sk-[A-Za-z0-9]{16,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|"
    r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+|"
    r"postgres(?:ql)?\+?\w*://[^\s:]+:[^\s@]+@)"
)


def _redact(
    _logger: Any, _name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    for key in list(event_dict):
        if key.lower() in REDACTED_KEYS:
            event_dict[key] = _PLACEHOLDER
        elif isinstance(event_dict[key], str):
            event_dict[key] = _SECRET_SHAPED.sub(_PLACEHOLDER, event_dict[key])
    return event_dict


def configure_logging(
    *,
    json_output: bool = True,
    level: int = logging.INFO,
    stream: Any | None = None,
) -> None:
    """Install the structlog pipeline. Idempotent.

    ``stream`` exists so tests can capture real emitted output. Without it structlog
    caches the stderr handle at configure time and ``redirect_stderr`` sees nothing --
    which would make an "assert the secret is absent" test pass vacuously.
    """
    renderer: Any = (
        structlog.processors.JSONRenderer()
        if json_output
        else structlog.dev.ConsoleRenderer(colors=False)
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _redact,
            structlog.processors.StackInfoRenderer(),
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(file=stream or sys.stderr),
        cache_logger_on_first_use=stream is None,
    )


def get_logger(name: str = "adai") -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)  # type: ignore[no-any-return]
