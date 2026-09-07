from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin, exceptions
from fastapi_users.authentication import AuthenticationBackend, CookieTransport
from fastapi_users.authentication.strategy.db import DatabaseStrategy
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from fastapi_users_db_sqlalchemy.access_token import SQLAlchemyAccessTokenDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import auth_limits, csrf_cookie, make_csrf, require_csrf
from app.models.user import OwnerSession, User
from app.schemas.owner import UserCreate, UserRead
from app.services.email import ConsoleEmailSender


class UserManager(UUIDIDMixin, BaseUserManager[User, UUID]):
    reset_password_token_lifetime_seconds = 3600
    verification_token_lifetime_seconds = 86400

    def __init__(self, user_db, sender=None):
        super().__init__(user_db)
        self.sender = sender or ConsoleEmailSender()

    async def on_after_request_verify(self, user, token, request=None):
        await self.sender.send_verification(user.email, token)

    async def on_after_reset_password(self, user, token, request=None):
        await self.sender.send_password_reset(user.email, token)

    async def validate_password(self, password, user):
        if not 12 <= len(password) <= 128:
            raise exceptions.InvalidPasswordException(reason="Use 12–128 characters.")


async def get_user_manager(session: AsyncSession = Depends(get_session)):
    yield UserManager(SQLAlchemyUserDatabase(session, User))


async def get_strategy(request: Request, session: AsyncSession = Depends(get_session)):
    ttl = request.app.state.settings.owner_session_ttl_seconds
    return DatabaseStrategy(SQLAlchemyAccessTokenDatabase(session, OwnerSession), ttl)


def create_auth(settings):
    transport = CookieTransport(
        cookie_name="__Host-reviewflow_owner"
        if settings.app_env == "production"
        else "reviewflow_owner",
        cookie_max_age=settings.owner_session_ttl_seconds,
        cookie_secure=settings.app_env == "production",
        cookie_httponly=True,
        cookie_samesite="lax",
    )
    backend = AuthenticationBackend(name="owner", transport=transport, get_strategy=get_strategy)
    users = FastAPIUsers[User, UUID](get_user_manager, [backend])
    current_user = users.current_user(active=True)
    router = APIRouter(prefix="/api/auth", tags=["Owner authentication"])
    guarded = [Depends(require_csrf), Depends(auth_limits)]
    router.include_router(users.get_register_router(UserRead, UserCreate), dependencies=guarded)
    router.include_router(users.get_auth_router(backend), dependencies=guarded)
    router.include_router(users.get_verify_router(UserRead), dependencies=guarded)
    router.include_router(users.get_reset_password_router(), dependencies=guarded)

    @router.get("/me", response_model=UserRead)
    async def me(user: User = Depends(current_user)):
        return user

    @router.get("/csrf")
    async def csrf(request: Request, response: Response):
        nonce, token = make_csrf(request)
        response.set_cookie(
            csrf_cookie(request),
            nonce,
            max_age=3600,
            secure=settings.app_env == "production",
            httponly=True,
            samesite="lax",
        )
        return {"csrf_token": token}

    return router, current_user
