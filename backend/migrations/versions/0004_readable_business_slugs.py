"""Add readable public review slugs while retaining existing identifiers."""

from alembic import op

revision = "0004_readable_business_slugs"
down_revision = "0003_funnel_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE reviewflow.businesses ADD COLUMN public_slug varchar(64)")
    op.execute(
        """
        UPDATE reviewflow.businesses
        SET public_slug = left(
            trim(both '-' from regexp_replace(lower(name), '[^a-z0-9]+', '-', 'g')),
            48
        ) || '-' || left(public_identifier, 8)
        WHERE public_slug IS NULL
        """
    )
    op.execute(
        """
        UPDATE reviewflow.businesses
        SET public_slug = 'business-' || left(public_identifier, 8)
        WHERE public_slug IS NULL OR public_slug = '-' || left(public_identifier, 8)
        """
    )
    op.execute("ALTER TABLE reviewflow.businesses ALTER COLUMN public_slug SET NOT NULL")
    op.create_unique_constraint(
        "uq_businesses_public_slug", "businesses", ["public_slug"], schema="reviewflow"
    )
    op.create_check_constraint(
        "ck_businesses_public_slug_format",
        "businesses",
        "public_slug ~ '^[a-zA-Z0-9][a-zA-Z0-9-]*$'",
        schema="reviewflow",
    )


def downgrade() -> None:
    op.drop_constraint("ck_businesses_public_slug_format", "businesses", schema="reviewflow")
    op.drop_constraint("uq_businesses_public_slug", "businesses", schema="reviewflow")
    op.drop_column("businesses", "public_slug", schema="reviewflow")
