"""SQLAlchemy ORM models for the options-platform persistence layer.

These models use SQLAlchemy 2.x typed declarative style (``Mapped[]`` +
``mapped_column``). The schema covers instruments, positions, executed
trades, periodic portfolio snapshots, and volatility forecasts.

Design notes:
    * No business logic lives on the ORM classes — they are pure data
      containers. Anything that needs to query or mutate state goes through
      :mod:`options_platform.data.repository`.
    * Enum-valued columns are stored as their underlying string values
      (``Enum(..., native_enum=False)``) so the on-disk representation is
      portable across backends and easy to inspect with a SQL client.
    * ``created_at`` (and where applicable ``updated_at``) is recorded for
      every row to support audit and time-series queries.
    * Foreign keys cascade-delete child rows where the child has no meaning
      without its parent (positions, forecasts).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base shared by all ORM models in this module."""


def _string_enum(enum_cls: type, *, length: int) -> SAEnum:
    """``SAEnum`` configured to persist the ``value`` of each member.

    SQLAlchemy defaults to storing the enum member's *name* (e.g.
    ``"EQUITY"``). Persisting the *value* (``"equity"``) keeps the
    on-disk representation aligned with the legacy hand-written schema
    and is the convention used everywhere else in the codebase.
    """
    return SAEnum(
        enum_cls,
        native_enum=False,
        length=length,
        values_callable=lambda c: [e.value for e in c],
        validate_strings=True,
    )


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class AssetClass(str, Enum):
    """Coarse asset classification for an :class:`Instrument`."""

    EQUITY = "equity"
    OPTION = "option"


class OptionType(str, Enum):
    """Option right — call or put."""

    CALL = "call"
    PUT = "put"


class TradeSide(str, Enum):
    """Direction of an executed :class:`Trade`."""

    BUY = "buy"
    SELL = "sell"


class ForecastModel(str, Enum):
    """Volatility model family that produced a :class:`VolatilityForecast`."""

    HISTORICAL = "historical"
    EWMA = "ewma"
    GARCH = "garch"
    IMPLIED = "implied"
    REGIME = "regime"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class Instrument(Base):
    """An underlying equity or an option contract.

    A row represents a tradable instrument identified by ``symbol``. For
    options, ``option_type``, ``strike`` and ``expiry`` are populated; for
    equities these remain ``NULL``.
    """

    __tablename__ = "instruments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    asset_class: Mapped[AssetClass] = mapped_column(
        _string_enum(AssetClass, length=16),
        nullable=False,
    )
    underlying_symbol: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    option_type: Mapped[OptionType | None] = mapped_column(
        _string_enum(OptionType, length=8),
        nullable=True,
    )
    strike: Mapped[float | None] = mapped_column(Float, nullable=True)
    expiry: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    positions: Mapped[list[Position]] = relationship(
        back_populates="instrument",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    trades: Mapped[list[Trade]] = relationship(
        back_populates="instrument",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    forecasts: Mapped[list[VolatilityForecast]] = relationship(
        back_populates="instrument",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        Index("ix_instruments_expiry", "expiry"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return (
            f"Instrument(id={self.id!r}, symbol={self.symbol!r}, "
            f"asset_class={self.asset_class!r})"
        )


class Position(Base):
    """A single open position for one instrument.

    The position layer is a *current state* table — one row per instrument
    — kept in sync by the trading layer. Use :class:`Trade` for the
    immutable history of executions.
    """

    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("instruments.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    realized_pnl: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    instrument: Mapped[Instrument] = relationship(back_populates="positions")

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return (
            f"Position(instrument_id={self.instrument_id!r}, "
            f"quantity={self.quantity!r}, avg_cost={self.avg_cost!r})"
        )


class Trade(Base):
    """Immutable record of an executed buy/sell."""

    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("instruments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    side: Mapped[TradeSide] = mapped_column(
        _string_enum(TradeSide, length=8),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    fees: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    executed_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        index=True,
    )
    external_id: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    instrument: Mapped[Instrument] = relationship(back_populates="trades")

    __table_args__ = (
        Index("ix_trades_instrument_executed", "instrument_id", "executed_at"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return (
            f"Trade(instrument_id={self.instrument_id!r}, side={self.side!r}, "
            f"quantity={self.quantity!r}, price={self.price!r})"
        )


class PortfolioSnapshot(Base):
    """Periodic mark-to-market snapshot of the whole portfolio."""

    __tablename__ = "portfolio_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        index=True,
    )
    cash: Mapped[float] = mapped_column(Float, nullable=False)
    equity: Mapped[float] = mapped_column(Float, nullable=False)
    realized_pnl: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    unrealized_pnl: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    gross_exposure: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_exposure: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    __table_args__ = (
        Index("ix_portfolio_snapshots_ts_desc", ts.desc()),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return (
            f"PortfolioSnapshot(ts={self.ts!r}, cash={self.cash!r}, equity={self.equity!r})"
        )


class VolatilityForecast(Base):
    """One forecast of realised / implied volatility for an instrument.

    A row is produced each time a vol model runs. The combination of
    (instrument, model, horizon, generated_at) uniquely identifies a
    forecast so re-runs cannot silently overwrite history.
    """

    __tablename__ = "volatility_forecasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("instruments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    model: Mapped[ForecastModel] = mapped_column(
        _string_enum(ForecastModel, length=16),
        nullable=False,
    )
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    forecast_vol: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    instrument: Mapped[Instrument] = relationship(back_populates="forecasts")

    __table_args__ = (
        UniqueConstraint(
            "instrument_id",
            "model",
            "horizon_days",
            "generated_at",
            name="uq_forecast_natural_key",
        ),
        Index(
            "ix_forecasts_instrument_model_generated",
            "instrument_id",
            "model",
            "generated_at",
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return (
            f"VolatilityForecast(instrument_id={self.instrument_id!r}, "
            f"model={self.model!r}, horizon_days={self.horizon_days!r}, "
            f"forecast_vol={self.forecast_vol!r})"
        )


__all__ = [
    "AssetClass",
    "Base",
    "ForecastModel",
    "Instrument",
    "OptionType",
    "Position",
    "PortfolioSnapshot",
    "Trade",
    "TradeSide",
    "VolatilityForecast",
]
