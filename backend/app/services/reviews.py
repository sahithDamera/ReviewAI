"""Public review session lifecycle."""
# ruff: noqa: E501
import hashlib
import secrets
import time
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.schemas.review import ReviewInput

_PUBLIC_CACHE_TTL_SECONDS = 300
_public_cache: dict[str, tuple[float, dict]] = {}


def clear_public_business_cache(identifier: str | None = None) -> None:
    if identifier is None:
        _public_cache.clear()
    else:
        _public_cache.pop(identifier, None)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def public_business(session: AsyncSession, identifier: str):
    cached = _public_cache.get(identifier)
    if cached and cached[0] > time.monotonic():
        return cached[1]
    row = (
        (
            await session.execute(
                text("""
                SELECT b.public_identifier, b.public_slug, b.name, c.name AS category_name,
                       b.brand_tone, b.logo_url, b.status,
                       d.url AS google_review_url, d.owner_confirmed_at
                FROM reviewflow.businesses b
                JOIN reviewflow.business_categories c ON c.id=b.category_id
                JOIN reviewflow.business_google_destinations d ON d.business_id=b.id
                WHERE b.public_identifier=:identifier OR b.public_slug=:identifier
            """),
                {"identifier": identifier},
            )
        )
        .mappings()
        .first()
    )
    if row is None or row["status"] != "active" or row["owner_confirmed_at"] is None:
        raise HTTPException(404, "BUSINESS_UNAVAILABLE")
    attributes = (
        (
            await session.execute(
                text("""
                SELECT a.id, a.label
                FROM reviewflow.business_attributes ba
                JOIN reviewflow.experience_attributes a ON a.id=ba.attribute_id
                WHERE ba.business_id=(SELECT id FROM reviewflow.businesses
                                      WHERE public_identifier=:identifier OR public_slug=:identifier)
                  AND ba.enabled ORDER BY ba.display_order, a.display_order
            """),
                {"identifier": identifier},
            )
        )
        .mappings()
        .all()
    )
    result = {
        "public_identifier": row["public_identifier"],
        "public_slug": row["public_slug"],
        "name": row["name"],
        "category_name": row["category_name"],
        "brand_tone": row["brand_tone"],
        "logo_url": row["logo_url"],
        "google_review_url": row["google_review_url"],
        "attributes": attributes,
        "available": True,
    }
    _public_cache[identifier] = (time.monotonic() + _PUBLIC_CACHE_TTL_SECONDS, result)
    return result


async def create_session(session: AsyncSession, data, settings: Settings):
    business = await public_business(session, data.business_identifier)
    business_id = await session.scalar(
        text("SELECT id FROM reviewflow.businesses WHERE public_identifier=:identifier OR public_slug=:identifier"),
        {"identifier": data.business_identifier},
    )
    raw_token = secrets.token_urlsafe(32)
    expires = datetime.now(UTC) + timedelta(seconds=settings.review_session_ttl_seconds)
    session_id = uuid4()
    await session.execute(
        text("""
            INSERT INTO reviewflow.review_sessions
              (id,business_id,token_hash,entry_source,expires_at)
            VALUES (:id,:business,:token,:source,:expires)
        """),
        {
            "id": session_id,
            "business": business_id,
            "token": token_hash(raw_token),
            "source": data.entry_source,
            "expires": expires,
        },
    )
    if data.entry_source == "qr":
        await session.execute(
            text(
                "INSERT INTO reviewflow.analytics_events "
                "(business_id,session_id,event_type) VALUES (:business,:session,'QR_OPENED')"
            ),
            {"business": business_id, "session": session_id},
        )
    await session.commit()
    return {
        "session_token": raw_token,
        "expires_at": expires,
        "business": business,
        "input_version": 0,
        "rating": None,
        "selected_attributes": [],
        "customer_comment": None,
    }


async def load_session(session: AsyncSession, raw_token: str):
    row = (
        (
            await session.execute(
                text("""
                SELECT rs.id, rs.business_id, rs.expires_at, rs.input_version,
                       rs.rating, rs.selected_attributes, rs.customer_comment,
                       b.public_identifier
                FROM reviewflow.review_sessions rs
                JOIN reviewflow.businesses b ON b.id=rs.business_id
                WHERE rs.token_hash=:token
            """),
                {"token": token_hash(raw_token)},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise HTTPException(401, "REVIEW_SESSION_INVALID")
    if row["expires_at"] <= datetime.now(UTC):
        raise HTTPException(410, "REVIEW_SESSION_EXPIRED")
    business = await public_business(session, row["public_identifier"])
    return row, business


async def update_session(session: AsyncSession, raw_token: str, data: ReviewInput):
    row, business = await load_session(session, raw_token)
    if data.input_version != row["input_version"]:
        raise HTTPException(409, "REVIEW_INPUT_CHANGED")
    ids = [item.attribute_id for item in data.selected_attributes]
    if len(set(ids)) != len(ids):
        raise HTTPException(422, "ATTRIBUTES_INVALID")
    allowed = set(
        await session.scalars(
            text("""
                SELECT ba.attribute_id
                FROM reviewflow.business_attributes ba
                WHERE ba.business_id=:business AND ba.enabled
            """),
            {"business": row["business_id"]},
        )
    )
    if any(attribute_id not in allowed for attribute_id in ids):
        raise HTTPException(422, "ATTRIBUTES_INVALID")
    next_version = row["input_version"] + 1
    selected = [item.model_dump(mode="json") for item in data.selected_attributes]
    result = await session.execute(
        text("""
            UPDATE reviewflow.review_sessions
            SET rating=:rating, selected_attributes=CAST(:attributes AS jsonb),
                customer_comment=:comment, rated_at=CASE WHEN :rating IS NOT NULL AND rated_at IS NULL THEN now() ELSE rated_at END, input_version=:version
            WHERE id=:id AND input_version=:expected AND expires_at > now()
            RETURNING expires_at
        """),
        {
            "rating": data.rating,
            "attributes": __import__("json").dumps(selected),
            "comment": data.customer_comment,
            "version": next_version,
            "id": row["id"],
            "expected": data.input_version,
        },
    )
    if result.first() is None:
        await session.rollback()
        raise HTTPException(409, "REVIEW_INPUT_CHANGED")
    if data.rating is not None:
        await session.execute(
            text(
                "INSERT INTO reviewflow.analytics_events "
                "(business_id,session_id,event_type) "
                "VALUES (:business,:session,'RATING_SELECTED')"
            ),
            {"business": row["business_id"], "session": row["id"]},
        )
    if selected:
        await session.execute(
            text(
                "INSERT INTO reviewflow.analytics_events "
                "(business_id,session_id,event_type) "
                "VALUES (:business,:session,'ATTRIBUTES_SELECTED')"
            ),
            {"business": row["business_id"], "session": row["id"]},
        )
    await session.commit()
    return {
        "session_token": raw_token,
        "expires_at": row["expires_at"],
        "business": business,
        "input_version": next_version,
        "rating": data.rating,
        "selected_attributes": selected,
        "customer_comment": data.customer_comment,
    }
