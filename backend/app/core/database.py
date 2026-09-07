from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings


def connection_url(settings: Settings, *, migration: bool = False) -> URL:
    secret = settings.migration_database_url if migration else None
    url = make_url((secret or settings.database_url).get_secret_value())
    return url.set(drivername="postgresql+psycopg")


def connection_args(settings: Settings) -> dict:
    args = {
        "connect_timeout": settings.database_connect_timeout_seconds,
        "options": f"-c statement_timeout={settings.database_statement_timeout_ms}",
    }
    if settings.database_ssl_root_cert:
        args["sslrootcert"] = str(settings.database_ssl_root_cert)
    return args


def create_database_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(
        connection_url(settings),
        connect_args=connection_args(settings),
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_pre_ping=True,
        pool_timeout=5,
        hide_parameters=True,
        echo=False,
    )


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with factory() as session:
        yield session
