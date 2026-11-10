"""Shared test fixtures.

Two kinds of tests:
  * Plain tests — no database needed (auth, config, error format). Always run.
  * `db` tests — need a real PostgreSQL given by TEST_DATABASE_URL. They are skipped
    when it is not set (e.g. on a laptop without Postgres) and always run in CI.

DB tests are isolated: each test runs inside a transaction that is rolled back at the
end, so tests never see each other's data and the database stays clean.
"""

import os
import time
import uuid
from collections.abc import Callable, Iterator
from typing import Any

import jwt
import pytest
from alembic.config import Config
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

from alembic import command
from app.core.config import Settings
from app.core.db import get_db
from app.core.security import TokenVerifier
from app.main import create_app

SUPABASE_URL = "https://test-project.supabase.co"
ISSUER = f"{SUPABASE_URL}/auth/v1"
KEY_ID = "test-key-1"

TEST_DATABASE_URL = Settings(
    _env_file=None, database_url=os.getenv("TEST_DATABASE_URL")
).database_url


# ---------------------------------------------------------------- auth helpers


class _StaticKeySource:
    """Stands in for Supabase's JWKS endpoint: always returns our test public key."""

    def __init__(self, public_key: ec.EllipticCurvePublicKey) -> None:
        self._jwk = jwt.PyJWK.from_dict(
            {**jwt.algorithms.ECAlgorithm.to_jwk(public_key, as_dict=True), "kid": KEY_ID},
            algorithm="ES256",
        )

    def get_signing_key_from_jwt(self, token: str) -> jwt.PyJWK:
        if jwt.get_unverified_header(token).get("kid") != KEY_ID:
            raise jwt.PyJWKClientError("Unknown kid")
        return self._jwk


@pytest.fixture(scope="session")
def signing_key() -> ec.EllipticCurvePrivateKey:
    return ec.generate_private_key(ec.SECP256R1())


@pytest.fixture(scope="session")
def verifier(signing_key) -> TokenVerifier:
    return TokenVerifier(SUPABASE_URL, key_source=_StaticKeySource(signing_key.public_key()))


TokenFactory = Callable[..., str]


@pytest.fixture(scope="session")
def make_token(signing_key) -> TokenFactory:
    """Build a Supabase-style access token. Override any claim via kwargs."""

    def _make(user_id: uuid.UUID | str | None = None, **overrides: Any) -> str:
        now = int(time.time())
        claims: dict[str, Any] = {
            "sub": str(user_id or uuid.uuid4()),
            "aud": "authenticated",
            "iss": ISSUER,
            "role": "authenticated",
            "email": "test@example.com",
            "iat": now,
            "exp": now + 3600,
            **overrides,
        }
        claims = {k: v for k, v in claims.items() if v is not None}
        return jwt.encode(claims, signing_key, algorithm="ES256", headers={"kid": KEY_ID})

    return _make


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def build_app(verifier: TokenVerifier, **settings: Any):
    app = create_app(Settings(_env_file=None, **{"environment": "test", **settings}))
    app.state.token_verifier = verifier
    return app


@pytest.fixture
def client(verifier) -> TestClient:
    """App WITHOUT a database — for auth/config tests."""
    return TestClient(build_app(verifier))


# ------------------------------------------------------------------- database


def pytest_collection_modifyitems(config, items):
    if TEST_DATABASE_URL:
        return
    skip = pytest.mark.skip(reason="TEST_DATABASE_URL not set (DB tests run in CI)")
    for item in items:
        if "db" in item.keywords:
            item.add_marker(skip)


def pytest_configure(config):
    config.addinivalue_line("markers", "db: test needs a real PostgreSQL database")


@pytest.fixture(scope="session")
def db_engine() -> Iterator[Engine]:
    """Fresh schema built by running the real Alembic migrations."""
    assert TEST_DATABASE_URL
    engine = create_engine(TEST_DATABASE_URL, connect_args={"prepare_threshold": None})
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))

    cfg = Config("alembic.ini")
    cfg.attributes["database_url"] = TEST_DATABASE_URL
    command.upgrade(cfg, "head")

    yield engine
    engine.dispose()


@pytest.fixture
def db_connection(db_engine) -> Iterator[Connection]:
    with db_engine.connect() as conn:
        outer = conn.begin()
        yield conn
        outer.rollback()


@pytest.fixture
def db_session(db_connection) -> Iterator[Session]:
    # Commits inside app code become SAVEPOINT releases; the outer transaction is
    # still rolled back after the test.
    with Session(bind=db_connection, join_transaction_mode="create_savepoint") as session:
        yield session


@pytest.fixture
def db_client(verifier, db_connection) -> TestClient:
    """App wired to the test database (same rolled-back connection as db_session)."""
    app = build_app(verifier)

    def _get_test_db() -> Iterator[Session]:
        with Session(
            bind=db_connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        ) as session:
            yield session

    app.dependency_overrides[get_db] = _get_test_db
    return TestClient(app)
