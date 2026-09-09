"""
CareerMail AI — Database Engine & Session.

Uses SQLAlchemy 2.0 declarative style.
SQLite for local dev, PostgreSQL-compatible schema.
"""

from __future__ import annotations

from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


def _build_engine():
    """Create the SQLAlchemy engine from settings."""
    settings = get_settings()
    url = settings.DATABASE_URL

    connect_args: dict = {}
    if url.startswith("sqlite"):
        # SQLite needs this for FastAPI thread-safety.
        connect_args["check_same_thread"] = False

    engine = create_engine(
        url,
        connect_args=connect_args,
        pool_pre_ping=True,
        echo=False,
    )

    # Enable WAL mode and foreign keys for SQLite.
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _set_sqlite_pragmas(dbapi_conn, _connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


engine = _build_engine()

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables() -> None:
    """Create all tables (idempotent). Called at app startup."""
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as session:
        try:
            default_user = session.query(app.models.User).filter(app.models.User.id == 1).first()
            if not default_user:
                default_user = app.models.User(id=1, display_name="Default User")
                session.add(default_user)
                session.commit()
        except Exception:
            session.rollback()
