"""Database engine, ORM base class and the per-request session dependency.

We use *synchronous* SQLAlchemy 2.0 with psycopg 3. FastAPI runs sync endpoints in a
thread pool, which is plenty for this app and much easier to reason about than async.
"""

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import MetaData, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.errors import AppError

# Deterministic constraint names → Alembic migrations stay readable and reproducible.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def make_engine(database_url: str) -> Engine:
    return create_engine(
        database_url,
        pool_size=5,
        max_overflow=5,
        pool_pre_ping=True,  # survive Supabase/pooler dropping idle connections
        pool_recycle=300,
        connect_args={
            # Supabase's transaction pooler (port 6543) cannot use server-side prepared
            # statements. Disabling them is harmless on direct/session connections too.
            "prepare_threshold": None,
            "options": "-c timezone=UTC",
        },
    )


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    # expire_on_commit=False: objects stay readable after commit when building responses.
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db(request: Request) -> Iterator[Session]:
    """FastAPI dependency yielding one session per request.

    Services decide when to commit. Anything not committed is rolled back when the
    request ends, so a failed request can never leave half-written financial data.
    """
    factory: sessionmaker[Session] | None = getattr(request.app.state, "session_factory", None)
    if factory is None:
        raise AppError("database_not_configured", "DATABASE_URL is not set.", status_code=503)
    with factory() as session:
        yield session
