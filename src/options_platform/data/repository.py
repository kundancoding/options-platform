"""Repository layer over the ORM models.

Each repository wraps a SQLAlchemy ``Session`` and exposes the focused set
of operations the rest of the platform needs. Repositories never open or
close sessions themselves — that is the caller's responsibility (typically
via :func:`options_platform.data.database.session_scope`).

Conventions
-----------
* All write methods ``flush`` so the inserted row gets an ``id`` before the
  function returns, but **do not commit**. Commit semantics belong to the
  enclosing transaction scope so multiple repository calls can participate
  in one atomic unit of work.
* Read methods return ``None`` (or empty lists) on miss — they never raise
  for "not found".
* On any unexpected ``SQLAlchemyError`` the active transaction is rolled
  back before re-raising. This prevents a single failed insert from
  poisoning later operations on the same session.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import Generic, TypeVar

from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from options_platform.data.models import (
    Base,
    ForecastModel,
    Instrument,
    PortfolioSnapshot,
    Position,
    Trade,
    TradeSide,
    VolatilityForecast,
)
from options_platform.utils.logging import get_logger

logger = get_logger(__name__)

ModelT = TypeVar("ModelT", bound=Base)


# ---------------------------------------------------------------------------
# Base repository
# ---------------------------------------------------------------------------


class BaseRepository(Generic[ModelT]):
    """Shared CRUD primitives.

    Concrete repositories subclass this and bind ``model_cls`` to a single
    ORM class. The generic methods only handle bookkeeping that every
    table needs — domain-specific queries live on the subclasses.
    """

    model_cls: type[ModelT]

    def __init__(self, session: Session) -> None:
        self.session = session

    # -- helpers ----------------------------------------------------------

    def _safe_flush(self) -> None:
        """Flush the session, rolling back on error to keep state sane."""
        try:
            self.session.flush()
        except SQLAlchemyError:
            logger.exception(
                f"{type(self).__name__}: flush failed — rolling back transaction"
            )
            self.session.rollback()
            raise

    # -- CRUD -------------------------------------------------------------

    def add(self, entity: ModelT) -> ModelT:
        """Stage ``entity`` for insertion and flush so its PK is populated."""
        self.session.add(entity)
        self._safe_flush()
        return entity

    def bulk_add(self, entities: Iterable[ModelT]) -> list[ModelT]:
        """Insert many rows in one flush. Returns the persisted entities."""
        items = list(entities)
        if not items:
            return []
        self.session.add_all(items)
        self._safe_flush()
        return items

    def get(self, entity_id: int) -> ModelT | None:
        """Fetch a single row by primary key, or ``None`` if missing."""
        return self.session.get(self.model_cls, entity_id)

    def list_all(self, *, limit: int | None = None) -> list[ModelT]:
        """Return every row, optionally capped at ``limit``."""
        stmt = select(self.model_cls)
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.session.scalars(stmt))

    def delete(self, entity: ModelT) -> None:
        """Mark ``entity`` for deletion and flush."""
        self.session.delete(entity)
        self._safe_flush()

    def delete_by_id(self, entity_id: int) -> bool:
        """Delete the row with primary key ``entity_id``.

        Returns ``True`` if a row was removed, ``False`` otherwise.
        """
        entity = self.get(entity_id)
        if entity is None:
            return False
        self.delete(entity)
        return True

    def count(self) -> int:
        """Return the total number of rows in the table."""
        stmt = select(self.model_cls)
        return len(list(self.session.scalars(stmt)))


# ---------------------------------------------------------------------------
# Instrument repository (used internally by the others)
# ---------------------------------------------------------------------------


class InstrumentRepository(BaseRepository[Instrument]):
    """CRUD + symbol lookups for :class:`Instrument` rows."""

    model_cls = Instrument

    def get_by_symbol(self, symbol: str) -> Instrument | None:
        """Return the instrument matching ``symbol`` exactly, or ``None``."""
        stmt = select(Instrument).where(Instrument.symbol == symbol)
        return self.session.scalars(stmt).one_or_none()

    def get_or_create(self, symbol: str, **defaults: object) -> Instrument:
        """Fetch ``symbol`` or insert a new row with ``defaults`` set.

        ``defaults`` are only consulted when a new row is created.
        """
        existing = self.get_by_symbol(symbol)
        if existing is not None:
            return existing
        instrument = Instrument(symbol=symbol, **defaults)  # type: ignore[arg-type]
        return self.add(instrument)


# ---------------------------------------------------------------------------
# Position repository
# ---------------------------------------------------------------------------


class PositionRepository(BaseRepository[Position]):
    """Read / mutate the current holdings table."""

    model_cls = Position

    def get_by_instrument(self, instrument_id: int) -> Position | None:
        """Return the (unique) position for ``instrument_id``, or ``None``."""
        stmt = select(Position).where(Position.instrument_id == instrument_id)
        return self.session.scalars(stmt).one_or_none()

    def list_open(self) -> list[Position]:
        """Return all positions with non-zero quantity."""
        stmt = select(Position).where(Position.quantity != 0)
        return list(self.session.scalars(stmt))

    def upsert(
        self,
        instrument_id: int,
        *,
        quantity: int,
        avg_cost: float,
        realized_pnl: float = 0.0,
    ) -> Position:
        """Insert or update the position row for ``instrument_id``.

        SQLite lacks a portable ``ON CONFLICT`` for ORM updates, so we do
        the lookup / mutate / flush dance manually. Cheap because the
        ``positions.instrument_id`` index makes the lookup O(log n).
        """
        position = self.get_by_instrument(instrument_id)
        if position is None:
            position = Position(
                instrument_id=instrument_id,
                quantity=quantity,
                avg_cost=avg_cost,
                realized_pnl=realized_pnl,
            )
            self.session.add(position)
        else:
            position.quantity = quantity
            position.avg_cost = avg_cost
            position.realized_pnl = realized_pnl
        self._safe_flush()
        return position

    def delete_by_instrument(self, instrument_id: int) -> bool:
        """Remove the position row for ``instrument_id`` if any. """
        position = self.get_by_instrument(instrument_id)
        if position is None:
            return False
        self.delete(position)
        return True


# ---------------------------------------------------------------------------
# Trade repository
# ---------------------------------------------------------------------------


class TradeRepository(BaseRepository[Trade]):
    """Append-only log of executed trades + simple filters."""

    model_cls = Trade

    def record(
        self,
        *,
        instrument_id: int,
        side: TradeSide,
        quantity: int,
        price: float,
        fees: float = 0.0,
        executed_at: datetime | None = None,
        external_id: str | None = None,
    ) -> Trade:
        """Persist a single execution and return the inserted row."""
        if quantity <= 0:
            raise ValueError("Trade quantity must be positive")
        if price < 0:
            raise ValueError("Trade price must be non-negative")
        trade = Trade(
            instrument_id=instrument_id,
            side=side,
            quantity=quantity,
            price=price,
            fees=fees,
            external_id=external_id,
        )
        if executed_at is not None:
            trade.executed_at = executed_at
        return self.add(trade)

    def bulk_record(self, trades: Sequence[Trade]) -> list[Trade]:
        """Bulk-insert pre-built :class:`Trade` rows."""
        return self.bulk_add(trades)

    def list_by_instrument(
        self,
        instrument_id: int,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int | None = None,
    ) -> list[Trade]:
        """Return trades for ``instrument_id`` ordered by ``executed_at`` desc."""
        stmt = select(Trade).where(Trade.instrument_id == instrument_id)
        if since is not None:
            stmt = stmt.where(Trade.executed_at >= since)
        if until is not None:
            stmt = stmt.where(Trade.executed_at <= until)
        stmt = stmt.order_by(Trade.executed_at.desc())
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.session.scalars(stmt))

    def list_by_side(self, side: TradeSide, *, limit: int | None = None) -> list[Trade]:
        """Return trades filtered by side, most recent first."""
        stmt = select(Trade).where(Trade.side == side).order_by(Trade.executed_at.desc())
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.session.scalars(stmt))

    def get_by_external_id(self, external_id: str) -> Trade | None:
        """Look up a trade by its broker-assigned id."""
        stmt = select(Trade).where(Trade.external_id == external_id)
        return self.session.scalars(stmt).one_or_none()


# ---------------------------------------------------------------------------
# Forecast repository
# ---------------------------------------------------------------------------


class ForecastRepository(BaseRepository[VolatilityForecast]):
    """Persist and query volatility forecasts."""

    model_cls = VolatilityForecast

    def record(
        self,
        *,
        instrument_id: int,
        model: ForecastModel,
        horizon_days: int,
        forecast_vol: float,
        confidence_low: float | None = None,
        confidence_high: float | None = None,
        generated_at: datetime | None = None,
    ) -> VolatilityForecast:
        """Insert a single forecast row."""
        if horizon_days <= 0:
            raise ValueError("horizon_days must be positive")
        if forecast_vol < 0:
            raise ValueError("forecast_vol must be non-negative")
        forecast = VolatilityForecast(
            instrument_id=instrument_id,
            model=model,
            horizon_days=horizon_days,
            forecast_vol=forecast_vol,
            confidence_low=confidence_low,
            confidence_high=confidence_high,
        )
        if generated_at is not None:
            forecast.generated_at = generated_at
        return self.add(forecast)

    def bulk_record(self, forecasts: Sequence[VolatilityForecast]) -> list[VolatilityForecast]:
        """Insert many pre-built forecasts in a single flush."""
        return self.bulk_add(forecasts)

    def latest_for(
        self,
        instrument_id: int,
        *,
        model: ForecastModel | None = None,
        horizon_days: int | None = None,
    ) -> VolatilityForecast | None:
        """Return the most recent forecast matching the filters, if any."""
        stmt = select(VolatilityForecast).where(
            VolatilityForecast.instrument_id == instrument_id
        )
        if model is not None:
            stmt = stmt.where(VolatilityForecast.model == model)
        if horizon_days is not None:
            stmt = stmt.where(VolatilityForecast.horizon_days == horizon_days)
        stmt = stmt.order_by(VolatilityForecast.generated_at.desc()).limit(1)
        return self.session.scalars(stmt).first()

    def history_for(
        self,
        instrument_id: int,
        *,
        model: ForecastModel | None = None,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> list[VolatilityForecast]:
        """Return forecasts for ``instrument_id`` newest-first."""
        stmt = select(VolatilityForecast).where(
            VolatilityForecast.instrument_id == instrument_id
        )
        if model is not None:
            stmt = stmt.where(VolatilityForecast.model == model)
        if since is not None:
            stmt = stmt.where(VolatilityForecast.generated_at >= since)
        stmt = stmt.order_by(VolatilityForecast.generated_at.desc())
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.session.scalars(stmt))

    def purge_older_than(self, cutoff: datetime) -> int:
        """Delete forecasts generated before ``cutoff``. Returns row count."""
        stmt = delete(VolatilityForecast).where(VolatilityForecast.generated_at < cutoff)
        result = self.session.execute(stmt)
        self._safe_flush()
        return int(result.rowcount or 0)


# ---------------------------------------------------------------------------
# Portfolio repository
# ---------------------------------------------------------------------------


class PortfolioRepository(BaseRepository[PortfolioSnapshot]):
    """Append-only mark-to-market snapshots."""

    model_cls = PortfolioSnapshot

    def record_snapshot(
        self,
        *,
        cash: float,
        equity: float,
        realized_pnl: float = 0.0,
        unrealized_pnl: float = 0.0,
        gross_exposure: float | None = None,
        net_exposure: float | None = None,
        ts: datetime | None = None,
    ) -> PortfolioSnapshot:
        """Insert a portfolio snapshot row."""
        snapshot = PortfolioSnapshot(
            cash=cash,
            equity=equity,
            realized_pnl=realized_pnl,
            unrealized_pnl=unrealized_pnl,
            gross_exposure=gross_exposure,
            net_exposure=net_exposure,
        )
        if ts is not None:
            snapshot.ts = ts
        return self.add(snapshot)

    def bulk_record(self, snapshots: Sequence[PortfolioSnapshot]) -> list[PortfolioSnapshot]:
        """Insert many pre-built snapshots."""
        return self.bulk_add(snapshots)

    def latest(self) -> PortfolioSnapshot | None:
        """Return the most recent snapshot, or ``None`` if the table is empty."""
        stmt = select(PortfolioSnapshot).order_by(PortfolioSnapshot.ts.desc()).limit(1)
        return self.session.scalars(stmt).first()

    def history(
        self,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 500,
    ) -> list[PortfolioSnapshot]:
        """Return snapshots in the given window, newest first."""
        stmt = select(PortfolioSnapshot)
        if since is not None:
            stmt = stmt.where(PortfolioSnapshot.ts >= since)
        if until is not None:
            stmt = stmt.where(PortfolioSnapshot.ts <= until)
        stmt = stmt.order_by(PortfolioSnapshot.ts.desc()).limit(limit)
        return list(self.session.scalars(stmt))


__all__ = [
    "BaseRepository",
    "ForecastRepository",
    "InstrumentRepository",
    "PortfolioRepository",
    "PositionRepository",
    "TradeRepository",
]
