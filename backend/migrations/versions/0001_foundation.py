"""Private Supabase application schema; SQL is versioned with this revision."""

from pathlib import Path

from alembic import op

revision = "0001_foundation"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    sql = Path(__file__).with_suffix(".sql").read_text(encoding="utf-8")
    # This revision contains simple DDL only, with no function bodies/semicolon strings.
    for statement in sql.split(";"):
        if statement.strip():
            op.execute(statement)


def downgrade():
    for table in (
        "analytics_daily",
        "analytics_events",
        "review_selections",
        "review_generations",
        "review_sessions",
        "business_google_destinations",
        "business_attributes",
        "businesses",
        "experience_attributes",
        "business_categories",
        "users",
    ):
        op.execute(f"DROP TABLE reviewflow.{table}")
    # Preserve the schema and Alembic history; never cascade into unrelated Supabase objects.
