"""Alembic migration environment.

The database URL is read from the app settings (DATABASE_URL env var / .env),
so credentials never live in alembic.ini.

Usage:
    alembic upgrade head                          # apply migrations
    alembic revision --autogenerate -m "message"  # create a migration from model changes
"""

from logging.config import fileConfig

from sqlalchemy import create_engine, pool

import app.models  # noqa: F401  (registers every table on Base.metadata)
from alembic import context
from app.core.config import Settings
from app.core.db import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    # Tests pass an explicit URL through config attributes; otherwise use settings.
    url = config.attributes.get("database_url") or Settings().database_url
    if not url:
        raise RuntimeError("DATABASE_URL is not set — cannot run migrations.")
    return url


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of executing it:  alembic upgrade head --sql"""
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(
        get_url(), poolclass=pool.NullPool, connect_args={"prepare_threshold": None}
    )
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            # Only manage our own schema; ignore Supabase's auth/storage/etc. schemas.
            include_schemas=False,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
