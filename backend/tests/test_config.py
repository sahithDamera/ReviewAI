import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.database import connection_url

LOCAL = "postgresql://tester:unit-password-fixture@localhost:54322/reviewflow_test"


def settings(**kwargs):
    return Settings(_env_file=None, database_url=LOCAL, **kwargs)


def test_settings_normalize_driver_without_exposing_password():
    config = settings()
    assert connection_url(config).drivername == "postgresql+psycopg"
    assert "unit-password-fixture" not in repr(config)


@pytest.mark.parametrize(
    "url",
    [
        "sqlite:///test.db",
        "postgresql://user:secret@example.com:5432/postgres",
        "postgresql://user:secret@example.com:6543/postgres?sslmode=verify-full",
        "not-a-url-secret",
    ],
)
def test_invalid_connections_are_rejected_without_secret_in_message(url):
    with pytest.raises(ValidationError) as caught:
        Settings(_env_file=None, database_url=url)
    assert url not in str(caught.value)


def test_remote_supabase_requires_verified_tls():
    config = Settings(
        _env_file=None,
        database_url="postgresql://postgres.ref:secret@aws-0-region.pooler.supabase.com:5432/"
        "postgres?sslmode=verify-full",
    )
    assert connection_url(config).query["sslmode"] == "verify-full"


def test_production_requires_https_and_tls():
    with pytest.raises(ValidationError):
        settings(app_env="production")
    with pytest.raises(ValidationError):
        settings(app_env="production", app_url="https://app.example.com")


def test_empty_optional_environment_values():
    config = settings(migration_database_url="", database_ssl_root_cert="")
    assert config.migration_database_url is None
    assert config.database_ssl_root_cert is None


def test_migrations_can_use_separate_credentials():
    config = settings(migration_database_url=LOCAL.replace("tester", "migrator"))
    assert connection_url(config, migration=True).username == "migrator"
    assert connection_url(config).username == "tester"
