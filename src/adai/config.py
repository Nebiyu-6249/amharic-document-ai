"""Application settings. Every value comes from the environment (control C-35).

No secret has a usable default. ``SECRET_KEY`` and ``DATABASE_URL`` have no defaults at
all, so a misconfigured deployment fails at import rather than silently running with a
known key.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ADAI_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    environment: Literal["dev", "test", "staging", "prod"] = "dev"
    debug: bool = False

    # --- secrets: no defaults, deliberately ---
    secret_key: SecretStr = Field(..., description="Session/CSRF signing key. 32+ bytes.")
    database_url: str = Field(..., description="postgresql+psycopg://user:pass@host/db")
    redis_url: str = "redis://localhost:6379/0"

    # --- transport & CORS (C-01..C-04) ---
    force_https: bool = True
    hsts_max_age: int = 63_072_000  # two years
    cors_allow_origins: Annotated[tuple[str, ...], NoDecode] = ()

    # --- uploads (C-27, C-28) ---
    max_upload_bytes: int = 15 * 1024 * 1024
    max_image_pixels: int = 40_000_000
    max_image_dimension: int = 12_000
    allowed_upload_types: Annotated[tuple[str, ...], NoDecode] = (
        "image/jpeg",
        "image/png",
        "image/webp",
    )
    blob_root: str = "/var/lib/adai/blobs"

    # --- retention (Q-5) ---
    original_retention_days: int = 90

    # --- AI (C-31..C-33), OpenAI per Q-3 ---
    openai_api_key: SecretStr | None = None
    llm_postcorrection_enabled: bool = False  # ADR-0009: off by default
    llm_daily_spend_cap_usd: float = 5.0
    llm_max_tokens_per_request: int = 2_000
    user_daily_job_quota: int = 50

    # --- pipeline ---
    pipeline_mode: Literal["stub", "full"] = "stub"

    @field_validator("cors_allow_origins", "allowed_upload_types", mode="before")
    @classmethod
    def _split_csv(cls, v: object) -> object:
        """Accept comma-separated env values, not just JSON.

        pydantic-settings JSON-decodes complex types *before* validators run, so
        ADAI_CORS_ALLOW_ORIGINS=https://a.example,https://b.example is a startup crash
        unless the field is annotated NoDecode. The .env.example documents the comma
        form, so both the annotation and this validator are required.
        """
        if isinstance(v, str):
            return tuple(part.strip() for part in v.split(",") if part.strip())
        return v

    @field_validator("secret_key")
    @classmethod
    def _key_long_enough(cls, v: SecretStr) -> SecretStr:
        if len(v.get_secret_value()) < 32:
            raise ValueError("ADAI_SECRET_KEY must be at least 32 characters")
        return v

    @field_validator("cors_allow_origins")
    @classmethod
    def _no_wildcard(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        # C-04: an explicit allowlist. A wildcard here would silently defeat the control.
        if any(origin.strip() == "*" for origin in v):
            raise ValueError("wildcard CORS origin is forbidden (control C-04)")
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
