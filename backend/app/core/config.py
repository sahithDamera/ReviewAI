from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def validate_database_url(value: SecretStr) -> SecretStr:
    try:
        url = make_url(value.get_secret_value())
        if url.drivername not in {"postgresql", "postgresql+psycopg"}:
            raise ValueError
        if not url.host or not url.database or not url.username:
            raise ValueError
        # Transaction pooling is deliberately unsupported in this foundation.
        if url.port == 6543:
            raise ValueError
        local = url.host in {"localhost", "127.0.0.1", "::1"}
        if not local and url.query.get("sslmode") != "verify-full":
            raise ValueError
    except Exception:
        raise ValueError(
            "Use a PostgreSQL direct/session URL (not port 6543); "
            "remote connections require sslmode=verify-full"
        ) from None
    return value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    app_env: Literal["development", "test", "production"] = "development"
    app_url: str = "http://localhost:3000"
    auth_secret: SecretStr | None = None
    owner_session_ttl_seconds: int = Field(default=43200, ge=60, le=604800)
    review_session_ttl_seconds: int = Field(default=7200, ge=3600, le=604800)
    database_url: SecretStr
    migration_database_url: SecretStr | None = None
    database_ssl_root_cert: Path | None = None
    database_pool_size: int = Field(default=3, ge=1, le=20)
    database_max_overflow: int = Field(default=2, ge=0, le=20)
    database_connect_timeout_seconds: int = Field(default=5, ge=1, le=30)
    database_statement_timeout_ms: int = Field(default=5000, ge=100, le=60000)
    generation_enabled: bool = True
    ai_provider: Literal["anthropic", "template"] = "anthropic"
    ai_model: str = "claude-haiku-4-5-20251001"
    ai_api_key: SecretStr | None = None
    ai_timeout_seconds: float = Field(default=6, ge=1, le=30)
    business_daily_generation_limit: int = Field(default=300, ge=1, le=100000)

    _database_url_valid = field_validator("database_url")(validate_database_url)

    @field_validator(
        "migration_database_url",
        "database_ssl_root_cert",
        "auth_secret",
        "ai_api_key",
        mode="before",
    )
    @classmethod
    def empty_is_none(cls, value):
        return None if value == "" else value

    @field_validator("migration_database_url")
    @classmethod
    def migration_url_valid(cls, value):
        return validate_database_url(value) if value is not None else None

    @model_validator(mode="after")
    def production_checks(self):
        parsed_origin = urlsplit(self.app_url)
        if (
            parsed_origin.scheme not in {"http", "https"}
            or not parsed_origin.netloc
            or parsed_origin.path
            or parsed_origin.query
            or parsed_origin.fragment
            or parsed_origin.username
        ):
            raise ValueError("APP_URL must be an exact HTTP(S) origin without a trailing slash")
        if self.auth_secret and len(self.auth_secret.get_secret_value()) < 32:
            raise ValueError("AUTH_SECRET must contain at least 32 characters")
        if self.database_ssl_root_cert and not self.database_ssl_root_cert.is_file():
            raise ValueError("DATABASE_SSL_ROOT_CERT must refer to an existing certificate")
        if self.app_env == "production":
            if not self.auth_secret:
                raise ValueError("Production requires a persistent AUTH_SECRET")
            if not self.app_url.startswith("https://"):
                raise ValueError("Production APP_URL requires HTTPS")
            if make_url(self.database_url.get_secret_value()).query.get("sslmode") != "verify-full":
                raise ValueError("Production database connections require verified TLS")
            if self.generation_enabled and self.ai_provider == "anthropic" and not self.ai_api_key:
                raise ValueError("Anthropic generation requires AI_API_KEY when enabled")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
