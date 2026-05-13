"""
FastAPI dependency injection providers.

All shared resources (DB sessions, config, loggers) are injected here.
This avoids global state and makes every handler independently testable.

Usage in route handlers:
    @router.get("/")
    def my_route(db: DbSession, config: AppConfig):
        ...
"""

from collections.abc import Generator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from backend.core.config import Settings
from backend.models.database import create_db_engine


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Load application settings (cached singleton).

    Uses lru_cache so .env is only read once, but can be overridden in tests
    by clearing the cache: get_settings.cache_clear()
    """
    settings = Settings()
    settings.ensure_directories()
    return settings


@lru_cache(maxsize=1)
def _get_session_factory() -> "sessionmaker[Session]":
    """Create the DB session factory (cached singleton)."""
    from sqlalchemy.orm import sessionmaker  # noqa: F811

    settings = get_settings()
    return create_db_engine(settings.database_url)


def get_db() -> Generator[Session, None, None]:
    """
    Yield a database session for a single request.

    The session is automatically closed after the request completes.
    """
    session_factory = _get_session_factory()
    db = session_factory()
    try:
        yield db
    finally:
        db.close()


# Type aliases for cleaner route handler signatures
AppConfig = Annotated[Settings, Depends(get_settings)]
DbSession = Annotated[Session, Depends(get_db)]
