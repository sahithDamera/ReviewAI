from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

BACKEND = Path(__file__).resolve().parents[1]


def test_offline_migration_compiles_all_tables(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost/reviewflow_test")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("MIGRATION_DATABASE_URL", "")
    get_settings.cache_clear()
    output = StringIO()
    config = Config(str(BACKEND / "alembic.ini"), stdout=output, output_buffer=output)
    try:
        command.upgrade(config, "head", sql=True)
    finally:
        get_settings.cache_clear()
    sql = output.getvalue()
    assert "CREATE TABLE reviewflow.businesses" in sql
    assert "CREATE TABLE reviewflow.review_sessions" in sql
    assert "ON DELETE SET NULL (session_id)" in sql
    assert "0001_foundation" in sql
    assert "CREATE TABLE public." not in sql
