"""Database engine and session helpers for authentication."""

from __future__ import annotations

from collections.abc import Generator, Iterator
from contextlib import contextmanager

from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.auth.settings import auth_settings, mask_database_url, require_auth_config

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine, _SessionLocal
    if _engine is not None:
        return _engine
    settings = require_auth_config()
    if not settings.database_url:
        raise RuntimeError("Authentication database is not configured.")
    try:
        _engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            future=True,
        )
        _SessionLocal = sessionmaker(
            bind=_engine, autoflush=False, autocommit=False, future=True
        )
        return _engine
    except Exception as exc:
        logger.error(
            "Authentication database connection failed ({})",
            mask_database_url(settings.database_url),
        )
        raise RuntimeError("Authentication database is unavailable.") from exc


def get_session_factory() -> sessionmaker[Session]:
    get_engine()
    assert _SessionLocal is not None
    return _SessionLocal


@contextmanager
def session_scope() -> Iterator[Session]:
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def db_session() -> Generator[Session, None, None]:
    """FastAPI dependency."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def check_database() -> None:
    """Raise if auth DB is unreachable. Safe to call when auth enabled."""
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))


def reset_engine_for_tests() -> None:
    """Dispose engine (tests only)."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None
    auth_settings.cache_clear()
