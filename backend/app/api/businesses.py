# ruff: noqa: E501
from datetime import date, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import require_csrf
from app.repositories.business import owned_profile
from app.schemas.analytics import AnalyticsReport
from app.schemas.dashboard import DashboardOverview
from app.schemas.owner import BusinessInput, BusinessRead, CategoryRead
from app.services.business import save_business
from app.services.qr_service import review_qr


def create_business_routes(current_user):
    router = APIRouter(prefix="/api", tags=["Businesses"])

    async def verified_owner(request: Request, user=Depends(current_user)):
        if request.app.state.settings.app_env == "production" and not user.is_verified:
            from fastapi import HTTPException
            raise HTTPException(403, "EMAIL_VERIFICATION_REQUIRED")
        return user

    @router.get("/business-categories", response_model=list[CategoryRead])
    async def categories(user=Depends(current_user), session: AsyncSession = Depends(get_session)):
        rows = (
            await session.execute(
                text("""
            SELECT c.id,c.name,a.id AS attribute_id,a.label
            FROM reviewflow.business_categories c
            JOIN reviewflow.experience_attributes a ON a.category_id=c.id
            WHERE c.is_active ORDER BY c.display_order,a.display_order
        """)
            )
        ).mappings()
        result = {}
        for row in rows:
            item = result.setdefault(
                row["id"], {"id": row["id"], "name": row["name"], "attributes": []}
            )
            item["attributes"].append({"id": row["attribute_id"], "label": row["label"]})
        return list(result.values())

    @router.get("/businesses/me", response_model=BusinessRead)
    async def mine(
        request: Request, user=Depends(current_user), session: AsyncSession = Depends(get_session)
    ):
        return await owned_profile(session, user.id, request.app.state.settings.app_url)

    @router.get("/businesses/{business_id}", response_model=BusinessRead)
    async def get_business(
        business_id: UUID,
        request: Request,
        user=Depends(verified_owner),
        session: AsyncSession = Depends(get_session),
    ):
        return await owned_profile(
            session, user.id, request.app.state.settings.app_url, business_id
        )

    @router.post(
        "/businesses",
        response_model=BusinessRead,
        status_code=201,
        dependencies=[Depends(require_csrf)],
    )
    async def create_business(
        data: BusinessInput,
        request: Request,
        user=Depends(verified_owner),
        session: AsyncSession = Depends(get_session),
    ):
        return await save_business(session, user.id, data, request.app.state.settings.app_url)

    @router.put(
        "/businesses/{business_id}",
        response_model=BusinessRead,
        dependencies=[Depends(require_csrf)],
    )
    async def update_business(
        business_id: UUID,
        data: BusinessInput,
        request: Request,
        user=Depends(current_user),
        session: AsyncSession = Depends(get_session),
    ):
        return await save_business(
            session, user.id, data, request.app.state.settings.app_url, business_id
        )

    @router.get("/businesses/{business_id}/qr")
    async def qr(
        business_id: UUID,
        request: Request,
        format: str = Query("png", pattern="^(png|svg)$"),
        user=Depends(current_user),
        session: AsyncSession = Depends(get_session),
    ):
        profile = await owned_profile(
            session, user.id, request.app.state.settings.app_url, business_id
        )
        qr_url = f"{profile['review_url']}{'&' if '?' in profile['review_url'] else '?'}source=qr"
        body, media_type, extension = review_qr(qr_url, format)
        return Response(
            content=body,
            media_type=media_type,
            headers={
                "Content-Disposition": (
                    f'attachment; filename="reviewflow-{profile["public_identifier"]}.{extension}"'
                ),
                "Cache-Control": "private, no-store",
            },
        )

    @router.get("/businesses/{business_id}/overview", response_model=DashboardOverview)
    async def overview(
        business_id: UUID,
        user=Depends(current_user),
        session: AsyncSession = Depends(get_session),
    ):
        await owned_profile(session, user.id, "", business_id)
        summary = (
            await session.execute(
                text("""
                    SELECT
                      COUNT(*) FILTER (WHERE event_type='QR_OPENED') AS review_link_opens,
                      COUNT(DISTINCT session_id) AS sessions,
                      COUNT(*) FILTER (WHERE event_type='AI_GENERATION_COMPLETED')
                        AS generations_completed,
                      COUNT(*) FILTER (WHERE event_type='REVIEW_SELECTED') AS reviews_selected,
                      COUNT(*) FILTER (WHERE event_type='COPY_SUCCEEDED') AS successful_copies,
                      COUNT(*) FILTER (WHERE event_type='GOOGLE_OPENED') AS google_handoff_clicks,
                      (SELECT AVG(rating)::float FROM reviewflow.review_sessions
                       WHERE business_id=:business AND rating IS NOT NULL) AS average_rating
                    FROM reviewflow.analytics_events WHERE business_id=:business
                """),
                {"business": business_id},
            )
        ).mappings().one()
        rows = (
            await session.execute(
                text("""
                    SELECT e.id,e.event_type,e.occurred_at,s.rating
                    FROM reviewflow.analytics_events e
                    LEFT JOIN reviewflow.review_sessions s ON s.id=e.session_id
                    WHERE e.business_id=:business
                    ORDER BY e.occurred_at DESC LIMIT 20
                """),
                {"business": business_id},
            )
        ).mappings().all()
        return {"summary": summary, "activity": rows}

    @router.get("/businesses/{business_id}/analytics", response_model=AnalyticsReport)
    async def analytics(
        business_id: UUID,
        from_date: date | None = Query(None, alias="from"),
        to_date: date | None = Query(None, alias="to"),
        user=Depends(current_user),
        session: AsyncSession = Depends(get_session),
    ):
        await owned_profile(session, user.id, "", business_id)
        end = to_date or date.today()
        start = from_date or (end - timedelta(days=29))
        if start > end or (end - start).days > 365:
            from fastapi import HTTPException
            raise HTTPException(422, "ANALYTICS_RANGE_INVALID")
        params = {"business": business_id, "start": start, "end": end}
        summary = (
            await session.execute(
                text("""
                    SELECT
                      COUNT(*) AS sessions,
                      COUNT(*) FILTER (WHERE rated_at IS NOT NULL) AS rated_sessions,
                      COUNT(*) FILTER (WHERE generated_at IS NOT NULL) AS generated_sessions,
                      COUNT(*) FILTER (WHERE selected_at IS NOT NULL) AS selected_sessions,
                      COUNT(*) FILTER (WHERE was_edited IS NOT NULL AND was_edited) AS manual_sessions,
                      COUNT(*) FILTER (WHERE copied_at IS NOT NULL) AS copied_sessions,
                      COUNT(*) FILTER (WHERE google_opened_at IS NOT NULL) AS google_handoff_sessions,
                      AVG(rating)::float AS rating_average
                    FROM reviewflow.review_sessions
                    WHERE business_id=:business AND created_at >= :start
                      AND created_at < (:end + INTERVAL '1 day')
                """), params,
            )
        ).mappings().one()
        daily = (
            await session.execute(
                text("""
                    SELECT date_trunc('day',e.occurred_at)::date AS day,
                      COUNT(DISTINCT e.session_id) AS sessions,
                      COUNT(DISTINCT e.session_id) FILTER (WHERE e.event_type='RATING_SELECTED') AS rated_sessions,
                      COUNT(DISTINCT e.session_id) FILTER (WHERE e.event_type='AI_GENERATION_COMPLETED') AS generated_sessions,
                      COUNT(DISTINCT e.session_id) FILTER (WHERE e.event_type='REVIEW_SELECTED') AS selected_sessions,
                      COUNT(DISTINCT rs.session_id) FILTER (WHERE rs.source='manual') AS manual_sessions,
                      COUNT(DISTINCT e.session_id) FILTER (WHERE e.event_type='COPY_SUCCEEDED') AS copied_sessions,
                      COUNT(DISTINCT e.session_id) FILTER (WHERE e.event_type='GOOGLE_OPENED') AS google_handoff_sessions,
                      COALESCE(SUM(DISTINCT r.rating),0)::integer AS rating_sum,
                      COUNT(DISTINCT r.id) FILTER (WHERE r.rating IS NOT NULL)::integer AS rating_count
                    FROM reviewflow.analytics_events e
                    LEFT JOIN reviewflow.review_sessions r ON r.id=e.session_id
                    LEFT JOIN reviewflow.review_selections rs ON rs.session_id=e.session_id
                    WHERE e.business_id=:business AND e.occurred_at >= :start
                      AND e.occurred_at < (:end + INTERVAL '1 day')
                    GROUP BY 1 ORDER BY 1
                """), params,
            )
        ).mappings().all()
        return {"start": start, "end": end, "summary": summary, "daily": daily}

    return router
