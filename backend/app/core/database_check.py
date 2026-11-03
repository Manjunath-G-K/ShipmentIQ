"""Database connectivity check used by the readiness endpoint."""

from sqlalchemy import text

from app.core.errors import DatabaseUnavailableError
from app.db.engine import get_engine


def check_database_connection() -> None:
    """Execute a real PostgreSQL query through the configured SQLAlchemy engine."""

    try:
        engine = get_engine()
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:
        # Do not expose the connection string or driver error to the API client.
        raise DatabaseUnavailableError() from exc
