"""Repository layer — thin CRUD facade over the ORM models.

Each repository accepts a SQLAlchemy ``Session`` and exposes the verbs we
actually need. Callers should not import :mod:`options_platform.data.models`
directly.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from options_platform.data.models import (
    FillRow,
    Instrument,
    OrderRow,
    PortfolioSnapshot,
    PositionRow,
    Quote,
)


@dataclass
class QuoteRepository:
    session: Session

    def latest(self, symbol: str) -> Quote | None:
        """Return the most recent quote for ``symbol``, or ``None``."""
        # TODO: SELECT ... ORDER BY ts DESC LIMIT 1.
        raise NotImplementedError

    def insert(self, quote: Quote) -> None:
        """Persist a new quote."""
        # TODO: session.add + flush.
        raise NotImplementedError


@dataclass
class OrderRepository:
    session: Session

    def save(self, order: OrderRow) -> None:
        """Upsert an order row."""
        raise NotImplementedError

    def record_fill(self, fill: FillRow) -> None:
        """Persist an executed fill and update the parent order."""
        raise NotImplementedError

    def list_open(self) -> list[OrderRow]:
        """Return all orders with status PENDING / PARTIAL."""
        raise NotImplementedError


@dataclass
class PositionRepository:
    session: Session

    def get(self, instrument: Instrument) -> PositionRow | None:
        raise NotImplementedError

    def upsert(self, position: PositionRow) -> None:
        raise NotImplementedError

    def all(self) -> list[PositionRow]:
        raise NotImplementedError


@dataclass
class PortfolioRepository:
    session: Session

    def snapshot(self, snapshot: PortfolioSnapshot) -> None:
        """Append a portfolio snapshot row."""
        raise NotImplementedError

    def history(self, limit: int = 500) -> list[PortfolioSnapshot]:
        """Return recent snapshots ordered by timestamp."""
        raise NotImplementedError
