from alembic import context
from sqlalchemy import create_engine, pool

from app.core.config import get_settings
from app.core.database import connection_args, connection_url

settings = get_settings()

if context.is_offline_mode():
    context.configure(
        url=connection_url(settings, migration=True),
        literal_binds=True,
        version_table_schema="reviewflow",
    )
    with context.begin_transaction():
        context.execute("CREATE SCHEMA IF NOT EXISTS reviewflow")
        context.run_migrations()
else:
    engine = create_engine(
        connection_url(settings, migration=True),
        poolclass=pool.NullPool,
        connect_args=connection_args(settings),
        hide_parameters=True,
    )
    try:
        with engine.connect() as connection:
            with connection.begin():
                connection.exec_driver_sql("CREATE SCHEMA IF NOT EXISTS reviewflow")
            context.configure(
                connection=connection,
                version_table_schema="reviewflow",
                # Explicit SQL migrations: incomplete phase models must not drive autogenerate.
                target_metadata=None,
                transaction_per_migration=True,
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()
