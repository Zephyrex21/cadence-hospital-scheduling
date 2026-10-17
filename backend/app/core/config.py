"""Application configuration.

Settings are read from environment variables (prefixed ``CADENCE_``) and an optional
``.env`` file. Storage is always UTC; ``clinic_timezone`` is for display only.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # Auth / JWT. The default secret is for development only and MUST be
    # overridden (CADENCE_JWT_SECRET) anywhere real.
    jwt_secret: str = "dev-insecure-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_ttl_min: int = 30
    refresh_token_ttl_min: int = 60 * 24 * 7  # 7 days

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.env.lower() in {"production", "prod"}


settings = Settings()
