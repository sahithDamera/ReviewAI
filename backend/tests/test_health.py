import logging
from contextlib import asynccontextmanager

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import SCHEMA_REVISION, create_app


class Engine:
    def __init__(self, revision=SCHEMA_REVISION, failure=False):
        self.revision = revision
        self.failure = failure

    @asynccontextmanager
    async def connect(self):
        if self.failure:
            raise RuntimeError("password=secret host=private")
        yield self

    async def scalar(self, statement):
        return self.revision


def client(engine):
    config = Settings(_env_file=None, database_url="postgresql://u:p@localhost/test")
    return TestClient(create_app(config, engine))


def test_liveness_does_not_require_database():
    with client(Engine(failure=True)) as browser:
        response = browser.get("/api/health/live")
        assert response.json() == {"status": "ok"}
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["x-request-id"]


def test_request_log_contains_safe_request_metadata(caplog):
    caplog.set_level(logging.INFO, logger="app.main")
    with client(Engine()) as browser:
        browser.get("/api/health/live")
    assert "request_complete" in caplog.text
    assert "GET" in caplog.text
    assert "request_id=" in caplog.text


def test_readiness_checks_revision():
    with client(Engine()) as browser:
        assert browser.get("/api/health/ready").json() == {"status": "ready"}
    with client(Engine(revision="old")) as browser:
        assert browser.get("/api/health/ready").status_code == 503


def test_readiness_redacts_database_failure(caplog):
    with client(Engine(failure=True)) as browser:
        response = browser.get("/api/health/ready")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "DATABASE_NOT_READY"
        assert response.json()["error"]["request_id"] == response.headers["x-request-id"]
        assert "secret" not in response.text + caplog.text
        assert "private" not in response.text + caplog.text
