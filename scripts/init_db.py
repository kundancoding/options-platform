"""Bootstrap (or validate) the options-platform SQLite database.

Usage::

    python scripts/init_db.py [--db PATH] [--drop] [--validate-only]

The script is idempotent: ``Base.metadata.create_all`` only issues
``CREATE TABLE`` statements for tables that don't already exist. Pass
``--drop`` to wipe and recreate the schema (destructive — confirms first).

After the schema is in place the script runs a startup validation pass
that compares the live tables against the ORM metadata and exits non-zero
if anything is missing.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import inspect

from options_platform.data.database import (
    DEFAULT_DB_PATH,
    Database,
    resolve_database_url,
)
from options_platform.data.models import Base
from options_platform.utils.logging import get_logger

logger = get_logger(__name__)


def _expected_tables() -> set[str]:
    """Tables that the ORM expects to exist after a successful init."""
    return set(Base.metadata.tables.keys())


def create_schema(database: Database, *, drop_first: bool = False) -> None:
    """Create all ORM tables on ``database`` (idempotent)."""
    if drop_first:
        logger.warning("Dropping all tables before recreate")
        Base.metadata.drop_all(database.engine)
    Base.metadata.create_all(database.engine)
    logger.info("Schema create_all completed")


def validate_schema(database: Database) -> list[str]:
    """Return a list of expected-but-missing table names (empty if healthy)."""
    inspector = inspect(database.engine)
    live = set(inspector.get_table_names())
    missing = sorted(_expected_tables() - live)
    if missing:
        logger.error(f"Schema validation FAILED — missing tables: {missing}")
    else:
        logger.info(f"Schema validation OK — {len(live)} tables present")
    return missing


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Initialise (or validate) the options-platform database."
    )
    parser.add_argument(
        "--db",
        type=str,
        default=None,
        help=(
            "SQLAlchemy URL or file path for the target database. Defaults to "
            f"sqlite:///{DEFAULT_DB_PATH} (overridable via OPTIONS_PLATFORM_DB)."
        ),
    )
    parser.add_argument(
        "--drop",
        action="store_true",
        help="Drop all tables before recreating. Destructive.",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Do not create anything; only verify the schema is healthy.",
    )
    return parser.parse_args(argv)


def _coerce_url(arg: str | None) -> str:
    """Translate a CLI value into a SQLAlchemy URL.

    A bare filesystem path becomes a ``sqlite:///`` URL; anything containing
    ``://`` is passed through. ``None`` defers to the regular resolution
    chain (env var → default path).
    """
    if arg is None:
        return resolve_database_url(None)
    if "://" in arg:
        return arg
    path = Path(arg).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path}"


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns a Unix-style exit code."""
    args = _parse_args(argv)
    url = _coerce_url(args.db)
    database = Database.create(url=url)
    try:
        if not args.validate_only:
            create_schema(database, drop_first=args.drop)
        missing = validate_schema(database)
        if missing:
            print(f"Schema validation failed — missing tables: {missing}", file=sys.stderr)
            return 1
        print(f"Database ready at {database.url}")
        return 0
    finally:
        database.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
