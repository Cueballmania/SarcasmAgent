"""Operating contract checks with synthetic settings only."""

import pytest
from pydantic import ValidationError

from app.config import Settings, database_url, public_url


def settings(**overrides: object) -> Settings:
    """Supply a secret-free isolated test configuration."""
    return Settings(
        _env_file=None,
        **{
            "database_url": "postgresql://localhost/sarcasm_test",
            "session_signing_key": "test-only-signing-key-with-32-characters",
            "app_env": "test",
            **overrides,
        },
    )


def test_production_requires_explicit_settings() -> None:
    with pytest.raises(ValidationError, match="Production requires explicit"):
        settings(app_env="production")


def test_related_bounds_and_secret_safety() -> None:
    with pytest.raises(ValidationError, match="exceed request deadline"):
        settings(stale_after_seconds=30, request_timeout_seconds=30)
    with pytest.raises(ValidationError, match="32 characters"):
        settings(session_signing_key="short")
    assert "test-only-signing" not in repr(settings())


def test_canonical_url_rejects_credentials_and_host_tricks() -> None:
    for value in [
        "http://example.test",
        "https://user:secret@example.test",
        "//evil.test",
        "https://example.test/?token=secret",
        "https://example.test/#x",
        "https://example.test:bad",
        "https://example.test:99999",
        "https://example.test:0",
        "https://bad host.test",
        "https://example.test/\n",
        "https://example.test/?",
    ]:
        with pytest.raises(ValueError):
            public_url(value)
    assert public_url("https://example.test") == "https://example.test/"
    assert public_url("https://example.test:8443") == "https://example.test:8443/"


def test_database_driver_preserves_tls_credentials() -> None:
    url = database_url("postgresql://u:p%40ss@localhost/db?sslmode=require")
    assert url.drivername == "postgresql+psycopg"
    assert url.password == "p@ss" and url.query["sslmode"] == "require"
    with pytest.raises(ValueError):
        database_url("sqlite:///fake.db")
