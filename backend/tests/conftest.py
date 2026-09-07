import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from app.core.config import get_settings
from app.core.runtime import event_loop_factory


def pytest_asyncio_loop_factories():
    return {"database-compatible": event_loop_factory}


@pytest.fixture(scope="module")
def database_url():
    raw = os.environ.get("TEST_DATABASE_URL")
    if not raw:
        pytest.skip("TEST_DATABASE_URL is not configured")
    url = make_url(raw).set(drivername="postgresql+psycopg")
    if url.host not in {"localhost", "127.0.0.1"} or url.database != "reviewflow_test":
        pytest.fail("Integration tests require a loopback database named reviewflow_test")
    return url


@pytest.fixture(scope="module")
def migrated(database_url):
    previous = {
        key: os.environ.get(key) for key in ("DATABASE_URL", "MIGRATION_DATABASE_URL", "APP_ENV")
    }
    os.environ["DATABASE_URL"] = database_url.render_as_string(hide_password=False)
    os.environ["MIGRATION_DATABASE_URL"] = ""
    os.environ["APP_ENV"] = "test"
    get_settings.cache_clear()
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    engine = create_engine(database_url)
    try:
        command.upgrade(config, "head")
        command.upgrade(config, "head")
        yield engine
    finally:
        engine.dispose()
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()
