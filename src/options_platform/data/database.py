"""SQLite engine and session management.

Uses SQLAlchemy 2.x style. The default database lives under ``data/`` in the
project root; the path can be overridden via the ``OPTIONS_PLATFORM_DB`` env
var.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "options_platform.db"


def _database_url() -> str:
    """Resolve the SQLAlchemy database URL from env or default path."""
    override = os.environ.get("OPTIONS_PLATFORM_DB")
    if override:
        return override
    DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{DEFAULT_DB_PATH}"


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Return a cached SQLAlchemy engine bound to the SQLite file."""
    return create_engine(
        _database_url(),
        echo=False,
        future=True,
        connect_args={"check_same_thread": False},
    )


@lru_cache(maxsize=1)
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)


def get_session() -> Session:
    """Open a new SQLAlchemy session."""
    return _session_factory()()
