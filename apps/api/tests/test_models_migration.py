"""Structural checks that don't need a live Postgres: every model compiles to
PG DDL, and the hand-written initial migration covers every table."""

from pathlib import Path

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app.models import Base

EXPECTED_TABLES = {
    "modules",
    "skills",
    "skill_edges",
    "skill_mappings",
    "papers",
    "paper_questions",
    "templates",
    "review_queue",
    "children",
    "attempts",
    "uploads",
    "child_state",
}

MIGRATION = Path(__file__).parents[1] / "alembic" / "versions" / "0001_initial_schema.py"


def test_all_expected_tables_modelled():
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_models_compile_to_postgres_ddl():
    for table in Base.metadata.sorted_tables:
        ddl = str(CreateTable(table).compile(dialect=postgresql.dialect()))
        assert f'"{table.name}"' in ddl or table.name in ddl


def test_initial_migration_covers_every_table():
    source = MIGRATION.read_text()
    for name in EXPECTED_TABLES:
        assert f'"{name}"' in source, f"migration is missing table {name}"
