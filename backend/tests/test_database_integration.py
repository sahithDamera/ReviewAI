"""Real SQL tests, never silently substitute SQLite for Supabase's PostgreSQL engine."""

from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.commands.seed import seed_defaults

pytestmark = pytest.mark.integration


async def test_seed_is_idempotent_and_preserves_edits(migrated, database_url):
    engine = create_async_engine(database_url)
    try:
        async with AsyncSession(engine) as session, session.begin():
            await seed_defaults(session)
            await session.execute(
                text(
                    "UPDATE reviewflow.business_categories SET name='Custom Cafe' WHERE slug='cafe'"
                )
            )
            await seed_defaults(session)
            assert (
                await session.scalar(text("SELECT count(*) FROM reviewflow.business_categories"))
                == 11
            )
            assert (
                await session.scalar(text("SELECT count(*) FROM reviewflow.experience_attributes"))
                == 55
            )
            assert (
                await session.scalar(
                    text("SELECT name FROM reviewflow.business_categories WHERE slug='cafe'")
                )
                == "Custom Cafe"
            )
            await session.execute(
                text("UPDATE reviewflow.business_categories SET name='Cafe' WHERE slug='cafe'")
            )
    finally:
        await engine.dispose()


def test_relational_constraints_and_expiry_cleanup(migrated):
    with migrated.connect() as connection, connection.begin():
        category = connection.scalar(
            text(
                "INSERT INTO reviewflow.business_categories(slug,name) "
                "VALUES (:slug,'Test') RETURNING id"
            ),
            {"slug": str(uuid4())},
        )
        owner = connection.scalar(
            text(
                "INSERT INTO reviewflow.users(email,password_hash) VALUES (:email,'test-hash') "
                "RETURNING id"
            ),
            {"email": f"{uuid4()}@example.test"},
        )
        business = connection.scalar(
            text(
                "INSERT INTO reviewflow.businesses(owner_id,name,category_id,public_identifier) "
                "VALUES (:owner,'Test',:category,:public) RETURNING id"
            ),
            {"owner": owner, "category": category, "public": uuid4().hex},
        )

        def session(rating):
            return connection.scalar(
                text(
                    "INSERT INTO reviewflow.review_sessions"
                    "(business_id,token_hash,rating,expires_at) "
                    "VALUES (:business,:token,:rating,now()+interval '2 hours') RETURNING id"
                ),
                {"business": business, "token": uuid4().hex + uuid4().hex, "rating": rating},
            )

        with pytest.raises(IntegrityError), connection.begin_nested():
            session(6)
        first, second = session(4), session(1)
        generation = connection.scalar(
            text(
                "INSERT INTO reviewflow.review_generations(session_id,request_key,input_version,"
                "input_snapshot,status,provider,model,prompt_version) "
                "VALUES (:session,'key',0,'{}','pending','fake','fake','v1') RETURNING id"
            ),
            {"session": first},
        )
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(
                text(
                    "INSERT INTO reviewflow.review_selections(session_id,generation_id,option_id,"
                    "source,final_text) VALUES (:session,:generation,'1','ai','Text')"
                ),
                {"session": second, "generation": generation},
            )
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(
                text(
                    "INSERT INTO reviewflow.review_generations"
                    "(session_id,request_key,input_version,"
                    "input_snapshot,status,provider,model,prompt_version) "
                    "VALUES (:session,'another',0,'{}','pending','fake','fake','v1')"
                ),
                {"session": first},
            )
        event = connection.scalar(
            text(
                "INSERT INTO reviewflow.analytics_events"
                "(business_id,session_id,event_type,dedupe_key) "
                "VALUES (:business,:session,'RATING_SELECTED','event') RETURNING id"
            ),
            {"business": business, "session": first},
        )
        connection.execute(
            text("DELETE FROM reviewflow.review_sessions WHERE id=:id"), {"id": first}
        )
        row = connection.execute(
            text("SELECT business_id,session_id FROM reviewflow.analytics_events WHERE id=:id"),
            {"id": event},
        ).one()
        assert row.business_id == business
        assert row.session_id is None


def test_schema_is_not_publicly_accessible(migrated):
    with migrated.connect() as connection:
        assert connection.scalar(
            text(
                "SELECT NOT EXISTS (SELECT 1 FROM pg_namespace n, "
                "LATERAL aclexplode(n.nspacl) a "
                "WHERE n.nspname='reviewflow' AND a.grantee=0)"
            )
        )


def test_migration_round_trip(migrated):
    # This module only accepts a dedicated local test database, never a hosted project.
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.downgrade(config, "base")
    with migrated.connect() as connection:
        assert connection.scalar(text("SELECT to_regclass('reviewflow.businesses')")) is None
    command.upgrade(config, "head")
    with migrated.connect() as connection:
        assert connection.scalar(text("SELECT to_regclass('reviewflow.businesses')")) is not None
