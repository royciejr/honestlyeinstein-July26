"""Async engine/session, created lazily so the app can boot (and /healthz can
answer) before DATABASE_URL is configured. One driver everywhere: psycopg3 via
SQLAlchemy's dual sync/async dialect — the app uses it async, Alembic and the
content loaders use it sync."""

from collections.abc import AsyncIterator

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .config import get_settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def normalize_database_url(url: str) -> str:
    """Coerce Neon/Heroku-style URLs onto the psycopg3 SQLAlchemy dialect."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        if not settings.database_url:
            raise HTTPException(status_code=503, detail="DATABASE_URL is not configured")
        _engine = create_async_engine(
            normalize_database_url(settings.database_url),
            pool_size=5,
            max_overflow=5,
            pool_pre_ping=True,  # absorbs Neon scale-to-zero cold starts
            pool_recycle=300,
        )
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _sessionmaker


async def get_session() -> AsyncIterator[AsyncSession]:
    async with get_sessionmaker()() as session:
        yield session
