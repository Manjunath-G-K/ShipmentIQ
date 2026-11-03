"""SQLAlchemy session dependency."""

from collections.abc import Generator

from sqlalchemy.orm import Session, sessionmaker

from app.db.engine import get_engine


def get_session_factory() -> sessionmaker[Session]:
    """Create a session factory bound to the configured engine."""

    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    """Yield a request-scoped SQLAlchemy session."""

    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
