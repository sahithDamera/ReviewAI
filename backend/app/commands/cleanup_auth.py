"""Remove expired owner sessions and authentication counters; schedule daily."""
import asyncio

from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import create_database_engine
from app.core.runtime import event_loop_factory


async def main():
    settings = get_settings()
    engine = create_database_engine(settings)
    try:
        async with engine.begin() as connection:
            await connection.execute(text(
                "DELETE FROM reviewflow.owner_sessions "
                "WHERE created_at < now()-make_interval(secs => :ttl)"
            ), {"ttl": settings.owner_session_ttl_seconds})
            await connection.execute(text(
                "DELETE FROM reviewflow.auth_rate_limits WHERE expires_at < now()"
            ))
        print("Expired owner sessions and authentication counters removed.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main(), loop_factory=event_loop_factory)
