"""Owner login sessions and shared authentication abuse limits."""

from alembic import op

revision = "0002_owners"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE reviewflow.users ADD COLUMN is_superuser boolean NOT NULL DEFAULT false"
    )
    op.execute("""CREATE TABLE reviewflow.owner_sessions (
        token varchar(43) PRIMARY KEY,
        user_id uuid NOT NULL REFERENCES reviewflow.users(id) ON DELETE CASCADE,
        created_at timestamptz NOT NULL DEFAULT now()
    )""")
    op.execute("CREATE INDEX owner_sessions_user_idx ON reviewflow.owner_sessions(user_id)")
    op.execute("CREATE INDEX owner_sessions_created_idx ON reviewflow.owner_sessions(created_at)")
    op.execute("""CREATE TABLE reviewflow.auth_rate_limits (
        key varchar(64) PRIMARY KEY,
        hits integer NOT NULL CHECK (hits > 0),
        expires_at timestamptz NOT NULL
    )""")
    op.execute(
        "CREATE INDEX auth_rate_limits_expiry_idx ON reviewflow.auth_rate_limits(expires_at)"
    )
    op.execute("REVOKE ALL ON reviewflow.owner_sessions, reviewflow.auth_rate_limits FROM PUBLIC")


def downgrade():
    op.execute("DROP TABLE reviewflow.auth_rate_limits")
    op.execute("DROP TABLE reviewflow.owner_sessions")
    op.execute("ALTER TABLE reviewflow.users DROP COLUMN is_superuser")
