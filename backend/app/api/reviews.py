from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import public_local_limits
from app.schemas.ai import GenerateRequest, GenerateResponse
from app.schemas.handoff import EventInput, SelectionInput, SelectionRead
from app.schemas.review import (
    PublicBusinessRead,
    ReviewInput,
    ReviewSessionCreate,
    ReviewSessionRead,
)
from app.services.generation import generate
from app.services.handoff import record_event, save_selection
from app.services.reviews import (
    create_session,
    load_session,
    public_business,
    update_session,
)

bearer = HTTPBearer(auto_error=False)


def create_review_routes(settings):
    router = APIRouter(
        prefix="/api/public", tags=["Public reviews"], dependencies=[Depends(public_local_limits)]
    )

    def session_token(credentials: HTTPAuthorizationCredentials | None):
        if credentials is None or credentials.scheme.lower() != "bearer":
            raise HTTPException(401, "REVIEW_SESSION_INVALID")
        return credentials.credentials

    @router.get("/business/{identifier}", response_model=PublicBusinessRead)
    async def business(identifier: str, session: AsyncSession = Depends(get_session)):
        return await public_business(session, identifier)

    @router.post("/review-session", response_model=ReviewSessionRead, status_code=201)
    async def start(data: ReviewSessionCreate, session: AsyncSession = Depends(get_session)):
        return await create_session(session, data, settings)

    @router.get("/review-session", response_model=ReviewSessionRead)
    async def restore(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
        session: AsyncSession = Depends(get_session),
    ):
        token = session_token(credentials)
        row, business_data = await load_session(session, token)
        return {"session_token": token, "expires_at": row["expires_at"], "business": business_data,
                "input_version": row["input_version"], "rating": row["rating"],
                "selected_attributes": row["selected_attributes"],
                "customer_comment": row["customer_comment"]}

    @router.patch("/review-session", response_model=ReviewSessionRead)
    async def update(
        data: ReviewInput,
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
        session: AsyncSession = Depends(get_session),
    ):
        return await update_session(session, session_token(credentials), data)

    @router.post("/generate-review", response_model=GenerateResponse)
    async def generate_review(
        data: GenerateRequest,
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
        idempotency_key: Annotated[str | None, Header()] = None,
        session: AsyncSession = Depends(get_session),
    ):
        if not idempotency_key:
            raise HTTPException(422, "IDEMPOTENCY_KEY_REQUIRED")
        return await generate(
            session, session_token(credentials), data.input_version, idempotency_key, settings
        )

    @router.post("/select-review", response_model=SelectionRead)
    async def select_review(
        data: SelectionInput,
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
        session: AsyncSession = Depends(get_session),
    ):
        return await save_selection(session, session_token(credentials), data)

    @router.post("/copy-event", status_code=204)
    async def copy_event(
        data: EventInput,
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
        session: AsyncSession = Depends(get_session),
    ):
        await record_event(session, session_token(credentials), "COPY_CLICKED", data)
        if data.outcome == "success":
            await record_event(
                session,
                session_token(credentials),
                "COPY_SUCCEEDED",
                EventInput(event_id=data.event_id, selection_id=data.selection_id),
            )

    @router.post("/google-open-event", status_code=204)
    async def google_open_event(
        data: EventInput,
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
        session: AsyncSession = Depends(get_session),
    ):
        await record_event(session, session_token(credentials), "GOOGLE_OPENED", data)

    return router
