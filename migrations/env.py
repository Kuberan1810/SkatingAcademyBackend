from logging.config import fileConfig

from alembic import context

from app.database.base import Base
from app.database.session import engine
from app.models import Admin, Batch

# Alembic Config object
config = context.config


# Configure Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


# SQLAlchemy metadata
# Alembic uses this to detect model changes
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Run migrations in offline mode.

    This generates SQL without opening a database connection.
    """

    url = str(engine.url)

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={
            "paramstyle": "named"
        },
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in online mode.

    This uses the SQLAlchemy engine configured
    in app/database/session.py.
    """

    with engine.connect() as connection:

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


# Choose migration mode
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()