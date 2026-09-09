"""
CareerMail AI — Test Configuration and Fixtures.

Uses a SINGLE-CONNECTION in-memory SQLite database for all tests.
The key insight: SQLite :memory: creates a new DB per connection,
so we use StaticPool to force all connections through one channel.
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# ── Set test environment BEFORE importing app modules ────────────
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["GOOGLE_CLIENT_ID"] = "test-client-id"
os.environ["GOOGLE_CLIENT_SECRET"] = "test-client-secret"
os.environ["GOOGLE_REDIRECT_URI"] = "http://localhost:8000/auth/google/callback"
os.environ["SCHEDULER_ENABLED"] = "false"

from cryptography.fernet import Fernet


_test_fernet_key = Fernet.generate_key().decode()
os.environ["ENCRYPTION_KEY"] = _test_fernet_key

# Now import app modules.
import app.database as db_module
from app.database import Base, get_db
from app.main import app

from fastapi.testclient import TestClient


@pytest.fixture(name="db_engine")
def fixture_db_engine():
    """Create a shared in-memory SQLite engine.

    Uses StaticPool so all connections share the same :memory: DB.
    This is the standard FastAPI testing pattern for SQLite.
    """
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(test_engine, "connect")
    def _set_sqlite_pragmas(dbapi_conn, _connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # Patch module-level engine and SessionLocal so lifespan and background jobs use ours.
    original_engine = db_module.engine
    original_session_local = db_module.SessionLocal
    db_module.engine = test_engine
    db_module.SessionLocal = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)

    Base.metadata.create_all(bind=test_engine)

    yield test_engine

    Base.metadata.drop_all(bind=test_engine)
    db_module.engine = original_engine
    db_module.SessionLocal = original_session_local
    test_engine.dispose()


@pytest.fixture(name="db")
def fixture_db(db_engine):
    """Provide a fresh DB session per test."""
    TestSession = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(name="client")
def fixture_client(db, db_engine):
    """Provide a FastAPI TestClient with overridden DB dependency."""

    def _override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
