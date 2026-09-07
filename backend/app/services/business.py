import re
import secrets
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.repositories.business import owned_profile
from app.services.reviews import clear_public_business_cache


def business_slug(name: str) -> str:
    readable = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "business"
    return readable[:64].rstrip("-")


async def save_business(session, owner_id, data, app_url, business_id=None):
    # Authentication may already have opened a transaction on this request's session.
    if data.status == "active" and not data.destination_confirmed:
        raise HTTPException(422, "DESTINATION_CONFIRMATION_REQUIRED")
    try:
        category = await session.scalar(
            text("SELECT id FROM reviewflow.business_categories WHERE id=:id AND is_active"),
            {"id": data.category_id},
        )
        if category is None:
            raise HTTPException(422, "CATEGORY_INVALID")
        old_category = None
        if business_id:
            existing = (
                await session.execute(
                    text(
                        "SELECT category_id FROM reviewflow.businesses "
                        "WHERE id=:id AND owner_id=:owner FOR UPDATE"
                    ),
                    {"id": business_id, "owner": owner_id},
                )
            ).first()
            if existing is None:
                raise HTTPException(404, "BUSINESS_NOT_FOUND")
            old_category = existing.category_id
        else:
            business_id = uuid4()
            public_identifier = secrets.token_urlsafe(24)
            base_slug = business_slug(data.name)
            duplicate_count = await session.scalar(
                text(
                    "SELECT count(*) FROM reviewflow.businesses "
                    "WHERE public_slug=:slug OR public_slug LIKE :prefix"
                ),
                {"slug": base_slug, "prefix": f"{base_slug}-%"},
            )
            public_slug = (
                base_slug
                if not duplicate_count
                else f"{base_slug[:61]}-{int(duplicate_count) + 1}"
            )
            await session.execute(
                text(
                    "INSERT INTO reviewflow.businesses"
                    "(id,owner_id,name,category_id,public_identifier,public_slug) "
                    "VALUES (:id,:owner,:name,:category,:public,:slug)"
                ),
                {
                    "id": business_id,
                    "owner": owner_id,
                    "name": data.name,
                    "category": data.category_id,
                    "public": public_identifier,
                    "slug": public_slug,
                },
            )
        await session.execute(
            text(
                "UPDATE reviewflow.businesses SET name=:name,category_id=:category,"
                "description=:description,brand_tone=:tone,status=:status,updated_at=now() "
                "WHERE id=:id AND owner_id=:owner"
            ),
            {
                "id": business_id,
                "owner": owner_id,
                "name": data.name,
                "category": data.category_id,
                "description": data.description,
                "tone": data.brand_tone,
                "status": data.status,
            },
        )
        await session.execute(
            text("""
            INSERT INTO reviewflow.business_google_destinations
                (business_id,url,validated_at,owner_confirmed_at)
            VALUES (:id,:url,now(),CASE WHEN :confirmed THEN now() ELSE NULL END)
            ON CONFLICT (business_id) DO UPDATE SET url=EXCLUDED.url,
                validated_at=now(),owner_confirmed_at=EXCLUDED.owner_confirmed_at,updated_at=now()
        """),
            {
                "id": business_id,
                "url": data.google_review_url,
                "confirmed": data.destination_confirmed,
            },
        )
        if old_category != data.category_id:
            await session.execute(
                text("DELETE FROM reviewflow.business_attributes WHERE business_id=:id"),
                {"id": business_id},
            )
            await session.execute(
                text(
                    "INSERT INTO reviewflow.business_attributes"
                    "(business_id,attribute_id,display_order) "
                    "SELECT :id,id,display_order FROM reviewflow.experience_attributes "
                    "WHERE category_id=:category"
                ),
                {"id": business_id, "category": data.category_id},
            )
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(409, "BUSINESS_ALREADY_EXISTS") from None
    profile = await owned_profile(session, owner_id, app_url, business_id)
    clear_public_business_cache(profile["public_identifier"])
    clear_public_business_cache(profile["public_slug"])
    return profile
