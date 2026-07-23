"""Database engine and session management for the options-platform.

This module owns the SQLAlchemy ``Engine`` and ``sessionmaker`` for the
SQLite backend and exposes safe, context-managed session helpers used by
the repository layer.

Two access patterns are supported:

* :func:`session_scope` — a ``with`` block that yields a session, commits
  on clean exit and rolls back on exception.
* :func:`get_session` — open a bare session for callers that need finer
  control. Such callers are responsible for ``commit`` / ``rollback`` /
  ``close``.

The default database file lives under ``data/options_platform.db`` at the
project root. Set the ``OPTIONS_PLATFORM_DB`` environment variable to an
arbitrary SQLAlchemy URL to override (``sqlite:///:memory:`` is handy for
tests).
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from options_platform.utils.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB_DIR = PROJECT_ROOT / "data"
DEFAULT_DB_PATH = DEFAULT_DB_DIR / "options_platform.db"
ENV_DB_URL = "OPTIONS_PLATFORM_DB"


def resolve_database_url(url: str | None = None) -> str:
    """Return the SQLAlchemy URL to use.

    Resolution order:
        1. Explicit ``url`` argument.
        2. ``OPTIONS_PLATFORM_DB`` environment variable.
        3. The bundled SQLite file at :data:`DEFAULT_DB_PATH`.
    """
    if url:
        return url
    env_url = os.environ.get(ENV_DB_URL)
    if env_url:
        return env_url
    DEFAULT_DB_DIR.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{DEFAULT_DB_PATH}"


# ---------------------------------------------------------------------------
# Engine + session factory abstraction
# ---------------------------------------------------------------------------


def _install_sqlite_pragmas(engine: Engine) -> None:
    """Apply SQLite tuning pragmas on every new connection.

    * ``foreign_keys=ON`` — enforce declared FK constraints.
    * ``busy_timeout=5000`` — wait up to 5 s for a contended writer lock
      before raising ``OperationalError`` (SQLite serialises writes; the
      timeout lets short concurrent writers from different sessions
      succeed instead of deadlocking instantly).
    """
    if not engine.url.get_backend_name().startswith("sqlite"):
        return

    @event.listens_for(engine, "connect")
    def _apply_pragmas(dbapi_connection: object, _: object) -> None:  # pragma: no cover - hook
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
        finally:
            cursor.close()


@dataclass(slots=True)
class Database:
    """Bundle of engine + session factory bound to a single URL.

    Use :meth:`session_scope` for transactional units of work. Most call
    sites should rely on the module-level helpers (:func:`session_scope`,
    :func:`get_session`) which delegate to a process-wide default
    :class:`Database`.
    """

    url: str
    engine: Engine
    session_factory: sessionmaker[Session]

    @classmethod
    def create(cls, url: str | None = None, *, echo: bool = False) -> Database:
        """Build a new :class:`Database` for ``url`` (or the resolved default)."""
        resolved = resolve_database_url(url)
        connect_args: dict[str, object] = {}
        if resolved.startswith("sqlite"):
            # SQLAlchemy's SQLite driver pins a connection to its creating
            # thread by default; relax that so the repository layer can be
            # used from worker threads (Streamlit, background tasks).
            connect_args["check_same_thread"] = False
        engine = create_engine(
            resolved,
            echo=echo,
            future=True,
            connect_args=connect_args,
        )
        _install_sqlite_pragmas(engine)
        factory: sessionmaker[Session] = sessionmaker(
            bind=engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
            future=True,
        )
        logger.info(f"Database engine initialised at url={resolved!r}")
        return cls(url=resolved, engine=engine, session_factory=factory)

    def session(self) -> Session:
        """Open a new bare session. Caller owns lifecycle."""
        return self.session_factory()

    @contextmanager
    def session_scope(self) -> Iterator[Session]:
        """Yield a session inside a transactional block.

        Commits on clean exit, rolls back if the body raises, and always
        closes the session. SQLAlchemy errors are logged and re-raised so
        callers can decide how to react.
        """
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except SQLAlchemyError:
            logger.exception("Transaction failed — rolling back")
            session.rollback()
            raise
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def connect(self) -> Connection:
        """Return a low-level engine connection (for schema work)."""
        return self.engine.connect()

    def dispose(self) -> None:
        """Release pooled connections (mostly useful in tests)."""
        self.engine.dispose()


# ---------------------------------------------------------------------------
# Process-wide default Database
# ---------------------------------------------------------------------------

_default_lock = Lock()
_default_database: Database | None = None


def get_database() -> Database:
    """Return (and lazily build) the process-wide default :class:`Database`."""
    global _default_database
    if _default_database is None:
        with _default_lock:
            if _default_database is None:
                _default_database = Database.create()
    return _default_database


def set_database(database: Database | None) -> None:
    """Replace (or clear) the process-wide default :class:`Database`.

    Intended for tests and CLI tools that need to swap in an in-memory or
    custom-URL database. Passing ``None`` resets the cache so the next
    :func:`get_database` call re-resolves from the environment.
    """
    global _default_database
    with _default_lock:
        if _default_database is not None and database is not _default_database:
            _default_database.dispose()
        _default_database = database


def get_engine() -> Engine:
    """Convenience accessor returning the default engine."""
    return get_database().engine


def get_session() -> Session:
    """Open a bare session against the default database.

    The caller is responsible for committing, rolling back and closing.
    Prefer :func:`session_scope` unless that lifecycle is inadequate.
    """
    return get_database().session()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Module-level shortcut for ``get_database().session_scope()``."""
    with get_database().session_scope() as session:
        yield session


__all__ = [
    "Database",
    "DEFAULT_DB_PATH",
    "ENV_DB_URL",
    "get_database",
    "get_engine",
    "get_session",
    "resolve_database_url",
    "session_scope",
    "set_database",
]
