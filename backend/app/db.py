"""SQLAlchemy engine + per-request session for Flask.

The session factory can be overridden per-app via `app.config["SESSION_FACTORY"]`
(used in tests). Otherwise it is built lazily from `DATABASE_URL`.
"""

from flask import current_app, g
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def _default_session_factory() -> sessionmaker[Session]:
    global _engine, _SessionLocal
    if _SessionLocal is None:
        settings = get_settings()
        _engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)
    return _SessionLocal


def get_session() -> Session:
    """Return the current request's session, creating it on first access."""
    if "db_session" not in g:
        factory = current_app.config.get("SESSION_FACTORY") or _default_session_factory()
        g.db_session = factory()
    return g.db_session


def close_session(exception: BaseException | None = None) -> None:
    session: Session | None = g.pop("db_session", None)
    if session is not None:
        session.close()
