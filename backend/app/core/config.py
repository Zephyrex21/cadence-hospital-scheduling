"""Application configuration.

Settings are read from environment variables (prefixed ``CADENCE_``) and an optional
``.env`` file. Storage is always UTC; ``clinic_timezone`` is for display only.
"""

from __future__ import annotations

import logging
import secrets

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_log = logging.getLogger("cadence.config")

# Secrets that have appeared in the public repo / docs and must never be trusted.
_KNOWN_INSECURE_SECRETS = {"", "dev-insecure-secret-change-me", "change-me", "secret"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CADENCE_",
        env_file=".env",
        extra="ignore",
    )

    app_name: str = "Cadence API"
    env: str = "development"
    clinic_timezone: str = "UTC"

    # Comma-separated list of allowed CORS origins.
    cors_origins: str = "http://localhost:5173"

    # Database. Default matches docker-compose credentials so local dev works
    # out of the box. Override with CADENCE_DATABASE_URL in other environments.
    database_url: str = (
        "postgresql+psycopg://cadence:cadence_dev_password@localhost:5432/cadence"
    )

    # Auth / JWT. There is deliberately NO usable default secret: if
    # CADENCE_JWT_SECRET is unset (or is a known-insecure value) outside
    # production a random per-process secret is generated (tokens then stop
    # working after a restart, which is safe); in production the app refuses to
    # start without a strong secret (>= 32 characters).
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    access_token_ttl_min: int = 30
    refresh_token_ttl_min: int = 60 * 24 * 7  # 7 days

    # The scheduling endpoints take an optional client-supplied ``now`` so tests
    # and the deterministic E2E can pin the clock. It MUST stay off in real
    # deployments: otherwise any caller could steer the engine's notion of time.
    allow_client_now: bool = False

    # Bring the database schema up to date automatically when the API starts
    # (``alembic upgrade head``). This is what lets a platform with no shell / release
    # step (e.g. Render free tier) deploy new code that needs a new column. A
    # PostgreSQL advisory lock makes concurrent instances take turns. Tests and the
    # E2E server (which build their own schema) turn it off.
    auto_migrate: bool = True

    # Login brute-force protection (per client-IP + email, and per email).
    login_max_attempts: int = 5
    login_window_sec: int = 15 * 60

    # Password for seeded demo staff. Required in production (the well-known
    # demo password is only used for local development).
    seed_password: str | None = None

    @model_validator(mode="after")
    def _validate_secrets(self) -> Settings:
        insecure = self.jwt_secret.strip() in _KNOWN_INSECURE_SECRETS
        if self.is_production:
            if insecure or len(self.jwt_secret) < 32:
                raise ValueError(
                    "CADENCE_JWT_SECRET must be set to a random value of at least 32 "
                    "characters when CADENCE_ENV=production"
                )
            if self.allow_client_now:
                raise ValueError("CADENCE_ALLOW_CLIENT_NOW must not be enabled in production")
        elif insecure:
            self.jwt_secret = secrets.token_urlsafe(48)
            _log.warning(
                "CADENCE_JWT_SECRET is not set; using a random per-process secret "
                "(sessions will not survive a restart)."
            )
        return self

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.env.lower() in {"production", "prod"}


settings = Settings()
