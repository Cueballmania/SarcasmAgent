"""Validated settings with explicit production bounds and no secret repr."""

import os
from typing import Self
from urllib.parse import urlsplit

from pydantic import (
    AliasChoices,
    Field,
    HttpUrl,
    SecretStr,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url

from app.contracts import MODEL


def database_url(value: str) -> URL:
    """Select Psycopg without losing credentials, TLS or other URL options."""
    url = make_url(value)
    if url.drivername not in {"postgres", "postgresql", "postgresql+psycopg"}:
        raise ValueError("DATABASE_URL must use PostgreSQL with Psycopg")
    return url.set(drivername="postgresql+psycopg")


def public_url(value: str) -> str:
    """Validate canonical HTTPS navigation, never a request Host header."""
    error = "PUBLIC_BASE_URL must be an absolute credential-free HTTPS root URL"
    try:
        parsed = urlsplit(value)
        canonical = HttpUrl(value)
    except (ValueError, ValidationError):
        raise ValueError(error) from None
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or "?" in value
        or "#" in value
        or canonical.port == 0
        or any(character.isspace() for character in value)
        or parsed.path not in {"", "/"}
    ):
        raise ValueError(error)
    return str(canonical)


class DatabaseSettings(BaseSettings):
    """Database-only configuration for migrations and maintenance."""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        hide_input_in_errors=True,
        populate_by_name=True,
    )
    database_url: SecretStr
    retention_days: int = Field(default=30, ge=1, le=365)
    stale_after_seconds: int = Field(default=60, ge=30, le=86400)
    maintenance_batch_size: int = Field(default=1000, ge=1, le=10000)

    @field_validator("database_url")
    @classmethod
    def valid_database(cls, value: SecretStr) -> SecretStr:
        """Reject non-PostgreSQL URLs without displaying credentials."""
        database_url(value.get_secret_value())
        return value


class Settings(DatabaseSettings):
    """App operating settings; production never invents approved quotas."""

    app_env: str = Field(
        default_factory=lambda: "production" if os.environ.get("RENDER") == "true" else "local"
    )
    openai_api_key: SecretStr | None = None
    langfuse_public_key: SecretStr | None = None
    langfuse_secret_key: SecretStr | None = None
    langfuse_base_url: str = "https://cloud.langfuse.com"
    session_signing_key: SecretStr
    public_base_url: str | None = None
    deploy_revision: str = Field(
        default="local",
        validation_alias=AliasChoices("DEPLOY_REVISION", "RENDER_GIT_COMMIT"),
    )
    model: str = MODEL
    global_window_limit: int = Field(default=30, ge=1, le=100000)
    global_day_limit: int = Field(default=300, ge=1, le=1000000)
    session_window_limit: int = Field(default=5, ge=1, le=10000)
    http_window_limit: int = Field(default=120, ge=1, le=100000)
    http_max_inflight: int = Field(default=8, ge=1, le=64)
    model_slots: int = Field(default=4, ge=1, le=16)
    audit_timeout_seconds: float = Field(default=2, gt=0, le=5)
    request_timeout_seconds: float = Field(default=20, gt=0, le=30)
    cleanup_grace_seconds: float = Field(default=5, gt=0, le=10)
    session_ttl_seconds: int = Field(default=3600, ge=60, le=86400)
    max_body_bytes: int = Field(default=16384, ge=256, le=16384)
    max_output_tokens: int = Field(default=128, ge=32, le=512)

    @field_validator("public_base_url")
    @classmethod
    def valid_public_url(cls, value: str | None) -> str | None:
        """Accept absent local URL, but never guess a deployed host."""
        return public_url(value) if value else None

    @field_validator("openai_api_key", "langfuse_public_key", "langfuse_secret_key", mode="before")
    @classmethod
    def absent_empty_keys(cls, value: object) -> object:
        """Blank example credentials are absent, never configured production clients."""
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator("langfuse_base_url")
    @classmethod
    def valid_trace_endpoint(cls, value: str) -> str:
        """Require HTTPS before sending project credentials to an endpoint."""
        return public_url(value).rstrip("/")

    @model_validator(mode="after")
    def operating_contract(self) -> Self:
        """Validate secret strength, related deadlines and explicit production settings."""
        if self.app_env not in {"local", "test", "production"}:
            raise ValueError("APP_ENV must be local, test or production")
        if os.environ.get("RENDER") == "true" and self.app_env != "production":
            raise ValueError("Render requires production mode and explicit operating settings")
        if len(self.session_signing_key.get_secret_value()) < 32:
            raise ValueError("SESSION_SIGNING_KEY must contain at least 32 characters")
        if self.model != MODEL:
            raise ValueError("MODEL must match the approved GPT-5.4 mini snapshot")
        if self.stale_after_seconds <= self.request_timeout_seconds + self.cleanup_grace_seconds:
            raise ValueError("STALE_AFTER_SECONDS must exceed request deadline plus cleanup grace")
        if self.session_window_limit > self.global_window_limit:
            raise ValueError("SESSION_WINDOW_LIMIT cannot exceed GLOBAL_WINDOW_LIMIT")
        if self.global_window_limit > self.global_day_limit:
            raise ValueError("GLOBAL_WINDOW_LIMIT cannot exceed GLOBAL_DAY_LIMIT")
        if self.app_env == "production":
            required = {
                "global_window_limit",
                "global_day_limit",
                "session_window_limit",
                "http_window_limit",
                "http_max_inflight",
                "audit_timeout_seconds",
                "retention_days",
                "session_ttl_seconds",
                "public_base_url",
            }
            if not required <= self.model_fields_set:
                raise ValueError(
                    "Production requires explicit URL, retention and admission settings"
                )
            if not all((self.openai_api_key, self.langfuse_public_key, self.langfuse_secret_key)):
                raise ValueError("Production requires OpenAI and Langfuse project credentials")
            if not self.public_base_url:
                raise ValueError("Production requires PUBLIC_BASE_URL")
            key = self.session_signing_key.get_secret_value()
            if key.startswith(("test", "example", "change")):
                raise ValueError("Production signing material must not be an example/test key")
        return self
