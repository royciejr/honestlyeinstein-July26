import os
import sys
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine, pool

# Make `app` importable whether alembic is invoked from apps/api or repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import normalize_database_url  # noqa: E402
from app.models import Base  # noqa: E402

target_metadata = Base.metadata


def _url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError("DATABASE_URL must be set to run migrations")
    return normalize_database_url(url)


def run_migrations_offline() -> None:
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Migrations run sync on the same psycopg3 driver the async app uses.
    engine = create_engine(_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
