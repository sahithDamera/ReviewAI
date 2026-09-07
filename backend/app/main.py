import asyncio
import logging
import secrets
import time
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from starlette.exceptions import HTTPException

from app.api.auth import create_auth
from app.api.businesses import create_business_routes
from app.api.reviews import create_review_routes
from app.core.config import Settings, get_settings
from app.core.database import create_database_engine

logger = logging.getLogger(__name__)
SCHEMA_REVISION = "0003_funnel_columns"


def create_app(settings: Settings | None = None, engine: AsyncEngine | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        database = engine if engine is not None else create_database_engine(settings)
        app.state.engine = database
        app.state.session_factory = async_sessionmaker(database, expire_on_commit=False)
        yield
        if engine is None:
            await database.dispose()

    app = FastAPI(
        title="ReviewFlow AI",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None if settings.app_env == "production" else "/api/docs",
        redoc_url=None,
        openapi_url=None if settings.app_env == "production" else "/api/openapi.json",
    )
    app.state.settings = settings
    app.state.auth_secret = (
        settings.auth_secret.get_secret_value()
        if settings.auth_secret
        else secrets.token_urlsafe(32)
    )
    auth_router, current_user = create_auth(settings)
    app.include_router(auth_router)
    app.include_router(create_business_routes(current_user))
    app.include_router(create_review_routes(settings))

    def error_response(request, status, code, message, headers=None):
        return JSONResponse(
            status_code=status,
            headers=headers,
            content={
                "error": {
                    "code": code,
                    "message": message,
                    "request_id": request.state.request_id,
                }
            },
        )

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        detail = (
            exc.detail if isinstance(exc.detail, str) else exc.detail.get("code", "REQUEST_FAILED")
        )
        return error_response(request, exc.status_code, detail, detail, exc.headers)

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request, exc):
        # Do not echo validation input (it may contain a submitted password).
        return error_response(
            request, 422, "VALIDATION_ERROR", "Check the form fields and try again."
        )

    @app.exception_handler(IntegrityError)
    async def conflict(request, exc):
        return error_response(
            request, 409, "ACCOUNT_CONFLICT", "An account with this email already exists."
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request, exc):
        return error_response(request, 503, "DATABASE_UNAVAILABLE", "Please try again shortly.")

    @app.middleware("http")
    async def response_headers(request: Request, call_next):
        request.state.request_id = str(uuid4())
        started = time.perf_counter()
        if request.method in {"POST", "PUT", "PATCH"}:
            if len(await request.body()) > 16384:
                return error_response(request, 413, "REQUEST_TOO_LARGE", "Request is too large.")
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "request_failed request_id=%s method=%s path=%s",
                request.state.request_id,
                request.method,
                request.url.path,
            )
            raise
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.info(
            "request_complete request_id=%s method=%s path=%s status=%s duration_ms=%s",
            request.state.request_id,
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Referrer-Policy"] = "no-referrer"
        if settings.app_env == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/health/live")
    async def live():
        return {"status": "ok"}

    @app.get("/api/health/ready")
    async def ready(request: Request):
        try:
            async with asyncio.timeout(settings.database_connect_timeout_seconds + 2):
                async with request.app.state.engine.connect() as connection:
                    revision = await connection.scalar(
                        text("SELECT version_num FROM reviewflow.alembic_version")
                    )
                    if revision != SCHEMA_REVISION:
                        raise RuntimeError("Schema revision mismatch")
            return {"status": "ready"}
        except Exception:
            # Connection errors may contain credentials or host details; never log them.
            logger.warning("Database readiness failed request_id=%s", request.state.request_id)
            return JSONResponse(
                status_code=503,
                content={
                    "error": {
                        "code": "DATABASE_NOT_READY",
                        "message": "Database is unavailable or migrations are pending.",
                        "request_id": request.state.request_id,
                    }
                },
            )

    return app
