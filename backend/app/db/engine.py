"""SQLAlchemy engine factory."""

from functools import lru_cache

from sqlalchemy import Engine, create_engine

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    """Create one process-level PostgreSQL engine from environment configuration."""

    settings = get_settings()
    return create_engine(
        settings.database_url,
        connect_args={"connect_timeout": settings.db_connect_timeout},
        pool_pre_ping=True,
    )
