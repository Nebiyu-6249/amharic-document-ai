"""Request and response schemas.

Two controls live here and both work by *omission*:

* C-20 -- request models are explicit allowlists. ``extra="forbid"`` means an attacker
  cannot smuggle ``owner_id`` or ``is_admin`` into a payload, and no request body is
  ever bound directly to an ORM model.
* C-21 -- response models list exactly what leaves the system. Password hashes, blob
  keys, internal paths and stack traces have no field to travel in.
"""

from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# --------------------------------------------------------------------------- requests


class RegisterRequest(StrictModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=256)


class LoginRequest(StrictModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class ConsentInput(StrictModel):
    """Consent captured at upload time (C-40, Q-2).

    ``research_opt_in`` is a separate decision from consenting to have the document
    transcribed, and defaults to False. ``subject_is_minor`` defaults to True because
    unknown must mean excluded.
    """

    lawful_basis: str = Field(default="consent", max_length=32)
    notice_version: str = Field(default="v1", max_length=32)
    research_opt_in: bool = False
    subject_is_minor: bool = True

    @field_validator("lawful_basis")
    @classmethod
    def _known_basis(cls, v: str) -> str:
        allowed = {"consent", "contract", "legitimate_interest"}
        if v not in allowed:
            raise ValueError(f"lawful_basis must be one of {sorted(allowed)}")
        return v


# -------------------------------------------------------------------------- responses


class UserOut(StrictModel):
    id: uuid.UUID
    email: EmailStr
    created_at: dt.datetime


class StageOut(StrictModel):
    stage: str
    method: str
    stub: bool
    stub_reason: str | None = None


class DocumentOut(StrictModel):
    """Note the absence of blob_key, sha256 and any filesystem path (C-21)."""

    id: uuid.UUID
    original_filename: str
    content_type: str
    byte_size: int
    width: int
    height: int
    status: str
    uploaded_at: dt.datetime
    originals_expire_at: dt.datetime


class TranscriptionOut(StrictModel):
    document_id: uuid.UUID
    schema_version: str
    markdown: str
    regions: list[dict[str, object]]
    #: Surfaced deliberately: a caller must be able to tell placeholder output from a
    #: real transcription without reading the docs.
    contains_stub_stages: bool
    stages: list[StageOut]
    pii_redacted: bool


class ErrorOut(StrictModel):
    """The only error shape the API emits. No stack traces, no internal detail."""

    detail: str
    code: str
