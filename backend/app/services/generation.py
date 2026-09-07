"""Review suggestion generation."""
# ruff: noqa: E501
import json
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ai_service import LLMProvider, ReviewContext, TemplateProvider
from app.services.reviews import load_session


async def generate(
    session: AsyncSession, raw_token: str, input_version: int, request_key: str, settings
):
    row, business = await load_session(session, raw_token)
    if input_version != row["input_version"]:
        raise HTTPException(409, "REVIEW_INPUT_CHANGED")
    if row["rating"] is None:
        raise HTTPException(422, "RATING_REQUIRED")
    if len(request_key) < 8 or len(request_key) > 100:
        raise HTTPException(422, "IDEMPOTENCY_KEY_INVALID")
    existing = (
        (
            await session.execute(
                text(
                    "SELECT id,status,reviews,input_version FROM reviewflow.review_generations "
                    "WHERE session_id=:session AND request_key=:key"
                ),
                {"session": row["id"], "key": request_key},
            )
        )
        .mappings()
        .first()
    )
    if existing is not None:
        if existing["status"] == "succeeded":
            return {
                "generation_id": str(existing["id"]),
                "input_version": existing["input_version"],
                "reviews": existing["reviews"],
            }
        raise HTTPException(409, "GENERATION_IN_PROGRESS")
    reserved = await session.execute(
        text("""
            UPDATE reviewflow.review_sessions
            SET generation_attempts=generation_attempts+1
            WHERE id=:id AND input_version=:version AND generation_attempts < 3
            RETURNING generation_attempts
        """),
        {"id": row["id"], "version": input_version},
    )
    if reserved.first() is None:
        await session.rollback()
        raise HTTPException(429, "GENERATION_LIMIT_REACHED")
    generation_id = uuid4()
    snapshot = {
        "rating": row["rating"],
        "selected_attributes": row["selected_attributes"],
        "customer_comment": row["customer_comment"],
    }
    try:
        await session.execute(
            text("""
                INSERT INTO reviewflow.review_generations
                  (id,session_id,request_key,input_version,input_snapshot,status,
                   provider,model,prompt_version)
                VALUES (:id,:session,:key,:version,CAST(:snapshot AS jsonb),'pending',
                        'local','deterministic-v1','phase5-v1')
            """),
            {
                "id": generation_id,
                "session": row["id"],
                "key": request_key,
                "version": input_version,
                "snapshot": json.dumps(snapshot),
            },
        )
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(409, "GENERATION_IN_PROGRESS") from None
    attributes = []
    for item in row["selected_attributes"]:
        label = next(
            (
                a["label"]
                for a in business["attributes"]
                if str(a["id"]) == str(item["attribute_id"])
            ),
            None,
        )
        if label:
            attributes.append((label, item["polarity"]))
    context = ReviewContext(
        business_name=business["name"],
        category=business["category_name"],
        rating=row["rating"],
        attributes=attributes,
        comment=row["customer_comment"],
        tone=business["brand_tone"],
    )
    ceiling = await session.scalar(
        text(
            "SELECT count(*) FROM reviewflow.review_generations g "
            "JOIN reviewflow.review_sessions s ON s.id=g.session_id "
            "WHERE s.business_id=:business AND g.status='succeeded' "
            "AND g.created_at >= current_date"
        ),
        {"business": row["business_id"]},
    )
    template = TemplateProvider()
    provider = template
    if (
        settings.generation_enabled
        and settings.ai_provider == "anthropic"
        and settings.ai_api_key
        and (ceiling or 0) < settings.business_daily_generation_limit
    ):
        provider = LLMProvider(
            settings.ai_api_key.get_secret_value(), settings.ai_model, settings.ai_timeout_seconds
        )
    await session.execute(
        text(
            "UPDATE reviewflow.review_sessions SET generated_at=COALESCE(generated_at, now()) WHERE id=:id"
        ),
        {"id": row["id"]},
    )
    await session.execute(
        text(
            "UPDATE reviewflow.review_generations SET provider=:provider, model=:model WHERE id=:id"
        ),
        {
            "provider": "anthropic" if isinstance(provider, LLMProvider) else "template",
            "model": settings.ai_model if isinstance(provider, LLMProvider) else "template-v1",
            "id": generation_id,
        },
    )
    try:
        reviews = await provider.generate(
            context, await _recent_openings(session, row["business_id"]), str(row["id"])
        )
    except Exception:
        reviews = await template.generate(context, (), str(row["id"]))
    await session.execute(
        text("""
            UPDATE reviewflow.review_generations
            SET status='succeeded', reviews=CAST(:reviews AS jsonb), updated_at=now()
            WHERE id=:id AND input_version=:version
        """),
        {"id": generation_id, "version": input_version, "reviews": json.dumps(reviews)},
    )
    await session.execute(
        text(
            "INSERT INTO reviewflow.analytics_events "
            "(business_id,session_id,event_type) "
            "VALUES (:business,:session,'AI_GENERATION_COMPLETED')"
        ),
        {"business": row["business_id"], "session": row["id"]},
    )
    await session.commit()
    return {"generation_id": str(generation_id), "input_version": input_version, "reviews": reviews}


async def _recent_openings(session: AsyncSession, business_id) -> list[str]:
    rows = await session.execute(
        text(
            "SELECT r.final_text FROM reviewflow.review_selections r "
            "JOIN reviewflow.review_sessions s ON s.id=r.session_id "
            "WHERE s.business_id=:business AND r.final_text IS NOT NULL "
            "ORDER BY r.created_at DESC LIMIT 20"
        ),
        {"business": business_id},
    )
    return [" ".join(str(row[0]).split()[:5]) for row in rows if row[0]]
