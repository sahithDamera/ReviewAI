"""Aggregate daily review activity and remove expired customer detail."""
# ruff: noqa: E501
import asyncio

from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import create_database_engine
from app.core.runtime import event_loop_factory


async def main():
    engine = create_database_engine(get_settings())
    try:
        async with engine.begin() as connection:
            await connection.execute(text("""
                INSERT INTO reviewflow.analytics_daily
                  (business_id,day,sessions,rated_sessions,generated_sessions,selected_sessions,
                   manual_sessions,copied_sessions,google_handoff_sessions,rating_sum,rating_count)
                SELECT e.business_id,date_trunc('day',e.occurred_at)::date,
                  COUNT(DISTINCT e.session_id),
                  COUNT(DISTINCT e.session_id) FILTER (WHERE e.event_type='RATING_SELECTED'),
                  COUNT(DISTINCT e.session_id) FILTER (WHERE e.event_type='AI_GENERATION_COMPLETED'),
                  COUNT(DISTINCT e.session_id) FILTER (WHERE e.event_type='REVIEW_SELECTED'),
                  COUNT(DISTINCT rs.session_id) FILTER (WHERE rs.source='manual'),
                  COUNT(DISTINCT e.session_id) FILTER (WHERE e.event_type='COPY_SUCCEEDED'),
                  COUNT(DISTINCT e.session_id) FILTER (WHERE e.event_type='GOOGLE_OPENED'),
                  COALESCE(SUM(DISTINCT r.rating),0), COUNT(DISTINCT r.id) FILTER (WHERE r.rating IS NOT NULL)
                FROM reviewflow.analytics_events e
                LEFT JOIN reviewflow.review_sessions r ON r.id=e.session_id
                LEFT JOIN reviewflow.review_selections rs ON rs.session_id=e.session_id
                WHERE e.occurred_at < current_date
                GROUP BY e.business_id,date_trunc('day',e.occurred_at)::date
                ON CONFLICT (business_id,day) DO UPDATE SET
                  sessions=EXCLUDED.sessions,rated_sessions=EXCLUDED.rated_sessions,
                  generated_sessions=EXCLUDED.generated_sessions,selected_sessions=EXCLUDED.selected_sessions,
                  manual_sessions=EXCLUDED.manual_sessions,copied_sessions=EXCLUDED.copied_sessions,
                  google_handoff_sessions=EXCLUDED.google_handoff_sessions,rating_sum=EXCLUDED.rating_sum,
                  rating_count=EXCLUDED.rating_count
            """))
            await connection.execute(text("DELETE FROM reviewflow.review_sessions WHERE expires_at < now()-interval '24 hours'"))
            await connection.execute(text("DELETE FROM reviewflow.analytics_events WHERE occurred_at < now()-interval '30 days'"))
            await connection.execute(text("DELETE FROM reviewflow.analytics_daily WHERE day < current_date-interval '12 months'"))
            await connection.execute(text("DELETE FROM reviewflow.auth_rate_limits WHERE expires_at < now()"))
        print("Review activity aggregated and expired detail removed.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main(), loop_factory=event_loop_factory)
