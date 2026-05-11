"""Bootstrap the local SQLite database from sql/schema.sql.

Usage::

    python scripts/init_db.py [--seed]

The script is idempotent — re-running it will only apply new migrations.
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = PROJECT_ROOT / "sql"
DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_DB_PATH = DATA_DIR / "options_platform.db"


def apply_schema(db_path: Path, seed: bool = False) -> None:
    """Create tables and (optionally) load seed data."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    schema_sql = (SQL_DIR / "schema.sql").read_text(encoding="utf-8")
    migration_sql = (SQL_DIR / "migrations" / "001_initial.sql").read_text(encoding="utf-8")

    with sqlite3.connect(db_path) as conn:
        conn.executescript(schema_sql)
        conn.executescript(migration_sql)
        if seed:
            seed_sql = (SQL_DIR / "seed.sql").read_text(encoding="utf-8")
            conn.executescript(seed_sql)
        conn.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize the options-platform SQLite DB.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Target DB path.")
    parser.add_argument("--seed", action="store_true", help="Also load sql/seed.sql.")
    args = parser.parse_args()

    apply_schema(args.db, seed=args.seed)
    print(f"Initialized {args.db}")


if __name__ == "__main__":
    main()
