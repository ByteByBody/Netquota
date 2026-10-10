"""Runtime configuration.

Values are read from environment variables (prefix ``NETQUOTA_``) and/or a
``.env`` file.  Defaults target local development with SQLite so the test suite
and a first run require no external services.  Production deployments use
PostgreSQL by setting ``NETQUOTA_DATABASE_URL``.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="NETQUOTA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Core ---------------------------------------------------------------
    app_name: str = "NetQuota"
    environment: str = "development"
    # SQLite by default; PostgreSQL in deployment.
    database_url: str = "sqlite+pysqlite:///./netquota.db"
    # Bind to loopback by default. The home server operator widens this
    # deliberately (see docs/privacy.md).
    bind_host: str = "127.0.0.1"
    bind_port: int = 8000

    # --- Security -----------------------------------------------------------
    # Secret used to sign administrator JWTs. MUST be overridden in production.
    jwt_secret: str = "dev-insecure-change-me"
    jwt_algorithm: str = "HS256"
    admin_token_ttl_minutes: int = 12 * 60

    # First-run bootstrap administrator. When ``admin_bootstrap_password`` is
    # set and no admin exists, it is created on startup.
    admin_bootstrap_username: str = "admin"
    admin_bootstrap_password: str | None = None

    # Device credential lifetime; agents rotate periodically.
    device_credential_ttl_days: int = 30
    enrollment_code_ttl_minutes: int = 30

    # --- Accounting ---------------------------------------------------------
    # A device is considered stale when it has not reported within this window.
    stale_after_minutes: int = 30
    # Reject samples whose observed_at is further than this into the future.
    max_clock_skew_seconds: int = 300
    # Interface selection policy: "primary" (default) or "all".
    interface_policy: str = Field(default="primary")

    # --- Rate limiting ------------------------------------------------------
    rate_limit_enroll_per_minute: int = 10
    rate_limit_auth_per_minute: int = 60

    # --- Misc ---------------------------------------------------------------
    seed_demo_data: bool = False

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()