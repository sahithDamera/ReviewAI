"""Denormalize review funnel milestones onto sessions."""
# ruff: noqa: E501

from alembic import op

revision = "0003_funnel_columns"
down_revision = "0002_owners"
branch_labels = None
depends_on = None


def upgrade():
    for column, kind in (
        ("rated_at", "timestamptz"),
        ("generated_at", "timestamptz"),
        ("selected_at", "timestamptz"),
        ("copied_at", "timestamptz"),
        ("google_opened_at", "timestamptz"),
        ("final_text_len", "integer"),
        ("was_edited", "boolean"),
    ):
        op.execute(f"ALTER TABLE reviewflow.review_sessions ADD COLUMN {column} {kind}")
    for column, event in (
        ("rated_at", "RATING_SELECTED"),
        ("generated_at", "AI_GENERATION_COMPLETED"),
        ("selected_at", "REVIEW_SELECTED"),
        ("copied_at", "COPY_SUCCEEDED"),
        ("google_opened_at", "GOOGLE_OPENED"),
    ):
        op.execute(
            f"UPDATE reviewflow.review_sessions s SET {column}=(SELECT min(occurred_at) FROM reviewflow.analytics_events e WHERE e.session_id=s.id AND e.event_type='{event}')"
        )
    op.execute(
        "UPDATE reviewflow.review_sessions s SET final_text_len=length(r.final_text), was_edited=r.is_edited FROM reviewflow.review_selections r WHERE r.session_id=s.id"
    )


def downgrade():
    for column in (
        "was_edited",
        "final_text_len",
        "google_opened_at",
        "copied_at",
        "selected_at",
        "generated_at",
        "rated_at",
    ):
        op.execute(f"ALTER TABLE reviewflow.review_sessions DROP COLUMN {column}")
