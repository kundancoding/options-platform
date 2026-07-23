"""Tests for the persistence layer.

These tests exercise the SQLAlchemy models, the session helpers and every
repository against an in-memory SQLite database. They cover:

* CRUD correctness for each entity.
* Transactional rollback when an error fires mid-flight.
* Bulk inserts and filtered queries.
* Foreign-key + uniqueness integrity.
* Relationship loading and cascade deletes.
* Concurrent session behaviour (two sessions on the same engine).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from options_platform.data.database import Database
from options_platform.data.models import (
    AssetClass,
    Base,
    ForecastModel,
    Instrument,
    OptionType,
    PortfolioSnapshot,
    Position,
    Trade,
    TradeSide,
)
from options_platform.data.repository import (
    ForecastRepository,
    InstrumentRepository,
    PortfolioRepository,
    PositionRepository,
    TradeRepository,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def database(tmp_path) -> Iterator[Database]:
    """Per-test SQLite database living in ``tmp_path``.

    Using a file (not ``:memory:``) lets us open multiple independent
    sessions that share the same store — critical for the concurrent-
    session tests.
    """
    db_path = tmp_path / "test.db"
    db = Database.create(url=f"sqlite:///{db_path}")
    Base.metadata.create_all(db.engine)
    try:
        yield db
    finally:
        db.dispose()


@pytest.fixture
def session(database: Database) -> Iterator[Session]:
    """Single short-lived session for tests that only need one.

    The session does NOT depend on any seeding fixture — seeding fixtures
    commit independently so they don't hold SQLite's write lock while
    this session runs.
    """
    with database.session_scope() as s:
        yield s


@pytest.fixture
def equity(database: Database) -> Instrument:
    """A persisted AAPL equity instrument.

    Committed in its own short transaction so the row exists in the DB
    file before the test's session is opened. The returned object is
    detached — only ``id`` and the originally-loaded scalar attributes
    are safe to read.
    """
    with database.session_scope() as s:
        return InstrumentRepository(s).get_or_create(
            "AAPL", asset_class=AssetClass.EQUITY
        )


@pytest.fixture
def option(database: Database) -> Instrument:
    """A persisted AAPL call option instrument (detached after commit)."""
    with database.session_scope() as s:
        return InstrumentRepository(s).get_or_create(
            "AAPL_240621C200",
            asset_class=AssetClass.OPTION,
            underlying_symbol="AAPL",
            option_type=OptionType.CALL,
            strike=200.0,
            expiry=datetime(2024, 6, 21),
        )


# ---------------------------------------------------------------------------
# Database / session helpers
# ---------------------------------------------------------------------------


class TestDatabase:
    def test_create_uses_resolved_url(self, tmp_path) -> None:
        db = Database.create(url=f"sqlite:///{tmp_path / 'x.db'}")
        try:
            assert db.url.endswith("x.db")
            assert db.engine is not None
        finally:
            db.dispose()

    def test_session_scope_commits_on_success(self, database: Database) -> None:
        with database.session_scope() as s:
            InstrumentRepository(s).get_or_create("MSFT", asset_class=AssetClass.EQUITY)

        with database.session_scope() as s:
            assert InstrumentRepository(s).get_by_symbol("MSFT") is not None

    def test_session_scope_rolls_back_on_error(self, database: Database) -> None:
        with pytest.raises(RuntimeError), database.session_scope() as s:
            InstrumentRepository(s).get_or_create("NVDA", asset_class=AssetClass.EQUITY)
            raise RuntimeError("boom")

        with database.session_scope() as s:
            assert InstrumentRepository(s).get_by_symbol("NVDA") is None

    def test_session_scope_rolls_back_on_integrity_error(self, database: Database) -> None:
        with database.session_scope() as s:
            InstrumentRepository(s).get_or_create("DUP", asset_class=AssetClass.EQUITY)

        with pytest.raises(IntegrityError), database.session_scope() as s:
            # Insert a duplicate symbol without going through get_or_create.
            s.add(Instrument(symbol="DUP", asset_class=AssetClass.EQUITY))

        with database.session_scope() as s:
            count = len(InstrumentRepository(s).list_all())
            assert count == 1


# ---------------------------------------------------------------------------
# Instrument repository
# ---------------------------------------------------------------------------


class TestInstrumentRepository:
    def test_add_assigns_primary_key(self, session: Session) -> None:
        repo = InstrumentRepository(session)
        inst = repo.add(Instrument(symbol="TSLA", asset_class=AssetClass.EQUITY))
        assert inst.id is not None

    def test_get_by_symbol_missing_returns_none(self, session: Session) -> None:
        assert InstrumentRepository(session).get_by_symbol("NOPE") is None

    def test_get_or_create_is_idempotent(self, session: Session) -> None:
        repo = InstrumentRepository(session)
        a = repo.get_or_create("GOOG", asset_class=AssetClass.EQUITY)
        b = repo.get_or_create("GOOG", asset_class=AssetClass.EQUITY)
        assert a.id == b.id

    def test_unique_symbol_enforced(self, database: Database) -> None:
        with database.session_scope() as s:
            s.add(Instrument(symbol="UNQ", asset_class=AssetClass.EQUITY))
        with pytest.raises(IntegrityError), database.session_scope() as s:
            s.add(Instrument(symbol="UNQ", asset_class=AssetClass.EQUITY))


# ---------------------------------------------------------------------------
# Position repository
# ---------------------------------------------------------------------------


class TestPositionRepository:
    def test_upsert_inserts_then_updates(
        self, session: Session, equity: Instrument
    ) -> None:
        repo = PositionRepository(session)

        pos = repo.upsert(equity.id, quantity=10, avg_cost=150.0)
        assert pos.id is not None
        assert pos.quantity == 10

        same = repo.upsert(equity.id, quantity=20, avg_cost=151.0, realized_pnl=5.0)
        assert same.id == pos.id
        assert same.quantity == 20
        assert same.avg_cost == 151.0
        assert same.realized_pnl == 5.0

    def test_get_by_instrument_returns_none_when_absent(
        self, session: Session, equity: Instrument
    ) -> None:
        assert PositionRepository(session).get_by_instrument(equity.id) is None

    def test_list_open_filters_zero_quantity(
        self, session: Session, equity: Instrument, option: Instrument
    ) -> None:
        repo = PositionRepository(session)
        repo.upsert(equity.id, quantity=5, avg_cost=100.0)
        repo.upsert(option.id, quantity=0, avg_cost=2.0)
        open_positions = repo.list_open()
        assert {p.instrument_id for p in open_positions} == {equity.id}

    def test_delete_by_instrument(
        self, session: Session, equity: Instrument
    ) -> None:
        repo = PositionRepository(session)
        repo.upsert(equity.id, quantity=1, avg_cost=1.0)
        assert repo.delete_by_instrument(equity.id) is True
        assert repo.get_by_instrument(equity.id) is None
        assert repo.delete_by_instrument(equity.id) is False

    def test_position_unique_per_instrument(
        self, database: Database, equity: Instrument
    ) -> None:
        with pytest.raises(IntegrityError), database.session_scope() as s:
            s.add(Position(instrument_id=equity.id, quantity=1, avg_cost=1.0))
            s.add(Position(instrument_id=equity.id, quantity=2, avg_cost=2.0))


# ---------------------------------------------------------------------------
# Trade repository
# ---------------------------------------------------------------------------


class TestTradeRepository:
    def test_record_and_fetch(self, session: Session, equity: Instrument) -> None:
        repo = TradeRepository(session)
        t = repo.record(
            instrument_id=equity.id,
            side=TradeSide.BUY,
            quantity=10,
            price=150.0,
            fees=1.0,
        )
        assert t.id is not None
        assert repo.get(t.id) is t

    @pytest.mark.parametrize("quantity,price", [(0, 1.0), (-1, 1.0), (1, -0.01)])
    def test_record_rejects_invalid_inputs(
        self, session: Session, equity: Instrument, quantity: int, price: float
    ) -> None:
        repo = TradeRepository(session)
        with pytest.raises(ValueError):
            repo.record(
                instrument_id=equity.id,
                side=TradeSide.BUY,
                quantity=quantity,
                price=price,
            )

    def test_bulk_record(self, session: Session, equity: Instrument) -> None:
        repo = TradeRepository(session)
        rows = [
            Trade(
                instrument_id=equity.id,
                side=TradeSide.BUY,
                quantity=1,
                price=float(i),
            )
            for i in range(5)
        ]
        out = repo.bulk_record(rows)
        assert len(out) == 5
        assert all(t.id is not None for t in out)

    def test_list_by_instrument_filters_window(
        self, session: Session, equity: Instrument
    ) -> None:
        repo = TradeRepository(session)
        base = datetime(2024, 1, 1, 9, 30)
        for i in range(4):
            repo.record(
                instrument_id=equity.id,
                side=TradeSide.BUY,
                quantity=1,
                price=100.0 + i,
                executed_at=base + timedelta(days=i),
            )

        since = base + timedelta(days=1)
        until = base + timedelta(days=2)
        in_window = repo.list_by_instrument(equity.id, since=since, until=until)
        assert len(in_window) == 2
        # Ordered newest-first.
        assert in_window[0].executed_at >= in_window[1].executed_at

    def test_list_by_side(self, session: Session, equity: Instrument) -> None:
        repo = TradeRepository(session)
        repo.record(instrument_id=equity.id, side=TradeSide.BUY, quantity=1, price=10.0)
        repo.record(instrument_id=equity.id, side=TradeSide.SELL, quantity=1, price=11.0)
        sells = repo.list_by_side(TradeSide.SELL)
        assert {t.side for t in sells} == {TradeSide.SELL}

    def test_external_id_unique(
        self, database: Database, equity: Instrument
    ) -> None:
        with database.session_scope() as s:
            TradeRepository(s).record(
                instrument_id=equity.id,
                side=TradeSide.BUY,
                quantity=1,
                price=1.0,
                external_id="ext-1",
            )
        with pytest.raises(IntegrityError), database.session_scope() as s:
            TradeRepository(s).record(
                instrument_id=equity.id,
                side=TradeSide.BUY,
                quantity=1,
                price=1.0,
                external_id="ext-1",
            )

    def test_get_by_external_id(
        self, session: Session, equity: Instrument
    ) -> None:
        repo = TradeRepository(session)
        repo.record(
            instrument_id=equity.id,
            side=TradeSide.BUY,
            quantity=1,
            price=1.0,
            external_id="brk-42",
        )
        hit = repo.get_by_external_id("brk-42")
        assert hit is not None and hit.external_id == "brk-42"
        assert repo.get_by_external_id("missing") is None


# ---------------------------------------------------------------------------
# Forecast repository
# ---------------------------------------------------------------------------


class TestForecastRepository:
    def test_record_returns_persisted_row(
        self, session: Session, equity: Instrument
    ) -> None:
        repo = ForecastRepository(session)
        f = repo.record(
            instrument_id=equity.id,
            model=ForecastModel.GARCH,
            horizon_days=10,
            forecast_vol=0.22,
        )
        assert f.id is not None
        assert f.model is ForecastModel.GARCH

    @pytest.mark.parametrize("horizon,vol", [(0, 0.2), (-1, 0.2), (5, -0.1)])
    def test_record_rejects_invalid(
        self, session: Session, equity: Instrument, horizon: int, vol: float
    ) -> None:
        repo = ForecastRepository(session)
        with pytest.raises(ValueError):
            repo.record(
                instrument_id=equity.id,
                model=ForecastModel.EWMA,
                horizon_days=horizon,
                forecast_vol=vol,
            )

    def test_latest_for_respects_filters(
        self, session: Session, equity: Instrument
    ) -> None:
        repo = ForecastRepository(session)
        base = datetime(2024, 5, 1)
        repo.record(
            instrument_id=equity.id,
            model=ForecastModel.GARCH,
            horizon_days=10,
            forecast_vol=0.20,
            generated_at=base,
        )
        repo.record(
            instrument_id=equity.id,
            model=ForecastModel.GARCH,
            horizon_days=10,
            forecast_vol=0.25,
            generated_at=base + timedelta(days=1),
        )
        repo.record(
            instrument_id=equity.id,
            model=ForecastModel.EWMA,
            horizon_days=10,
            forecast_vol=0.30,
            generated_at=base + timedelta(days=2),
        )

        latest_any = repo.latest_for(equity.id)
        assert latest_any is not None and latest_any.model is ForecastModel.EWMA

        latest_garch = repo.latest_for(equity.id, model=ForecastModel.GARCH)
        assert latest_garch is not None and latest_garch.forecast_vol == 0.25

    def test_history_for_orders_desc_and_limits(
        self, session: Session, equity: Instrument
    ) -> None:
        repo = ForecastRepository(session)
        base = datetime(2024, 5, 1)
        for i in range(5):
            repo.record(
                instrument_id=equity.id,
                model=ForecastModel.HISTORICAL,
                horizon_days=5,
                forecast_vol=0.10 + i * 0.01,
                generated_at=base + timedelta(days=i),
            )
        history = repo.history_for(equity.id, limit=3)
        assert len(history) == 3
        timestamps = [f.generated_at for f in history]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_natural_key_unique(
        self, database: Database, equity: Instrument
    ) -> None:
        ts = datetime(2024, 5, 1)
        with database.session_scope() as s:
            ForecastRepository(s).record(
                instrument_id=equity.id,
                model=ForecastModel.GARCH,
                horizon_days=10,
                forecast_vol=0.2,
                generated_at=ts,
            )
        with pytest.raises(IntegrityError), database.session_scope() as s:
            ForecastRepository(s).record(
                instrument_id=equity.id,
                model=ForecastModel.GARCH,
                horizon_days=10,
                forecast_vol=0.3,
                generated_at=ts,
            )

    def test_purge_older_than(
        self, session: Session, equity: Instrument
    ) -> None:
        repo = ForecastRepository(session)
        base = datetime(2024, 5, 1)
        for i in range(4):
            repo.record(
                instrument_id=equity.id,
                model=ForecastModel.EWMA,
                horizon_days=5,
                forecast_vol=0.2,
                generated_at=base + timedelta(days=i),
            )
        removed = repo.purge_older_than(base + timedelta(days=2))
        assert removed == 2
        remaining = repo.history_for(equity.id)
        assert len(remaining) == 2


# ---------------------------------------------------------------------------
# Portfolio repository
# ---------------------------------------------------------------------------


class TestPortfolioRepository:
    def test_record_and_latest(self, session: Session) -> None:
        repo = PortfolioRepository(session)
        repo.record_snapshot(
            cash=10_000.0,
            equity=12_000.0,
            ts=datetime(2024, 1, 1),
        )
        latest = repo.record_snapshot(
            cash=11_000.0,
            equity=13_000.0,
            ts=datetime(2024, 1, 2),
        )
        assert repo.latest() == latest

    def test_history_window(self, session: Session) -> None:
        repo = PortfolioRepository(session)
        base = datetime(2024, 1, 1)
        for i in range(5):
            repo.record_snapshot(
                cash=1000.0,
                equity=1000.0 + i,
                ts=base + timedelta(days=i),
            )
        window = repo.history(
            since=base + timedelta(days=1),
            until=base + timedelta(days=3),
        )
        assert [s.equity for s in window] == [1003.0, 1002.0, 1001.0]

    def test_bulk_record(self, session: Session) -> None:
        repo = PortfolioRepository(session)
        rows = [
            PortfolioSnapshot(cash=1.0, equity=2.0, ts=datetime(2024, 1, i + 1))
            for i in range(3)
        ]
        out = repo.bulk_record(rows)
        assert len(out) == 3
        assert repo.latest() is not None


# ---------------------------------------------------------------------------
# Relationship + cascade integrity
# ---------------------------------------------------------------------------


class TestRelationships:
    def test_instrument_relationship_loads_children(
        self, database: Database
    ) -> None:
        with database.session_scope() as s:
            inst = InstrumentRepository(s).get_or_create(
                "REL", asset_class=AssetClass.EQUITY
            )
            TradeRepository(s).record(
                instrument_id=inst.id, side=TradeSide.BUY, quantity=1, price=1.0
            )
            ForecastRepository(s).record(
                instrument_id=inst.id,
                model=ForecastModel.GARCH,
                horizon_days=10,
                forecast_vol=0.2,
            )
            PositionRepository(s).upsert(inst.id, quantity=1, avg_cost=1.0)

        with database.session_scope() as s:
            inst = InstrumentRepository(s).get_by_symbol("REL")
            assert inst is not None
            assert len(inst.trades) == 1
            assert len(inst.forecasts) == 1
            assert len(inst.positions) == 1

    def test_cascade_delete_clears_children(self, database: Database) -> None:
        with database.session_scope() as s:
            inst = InstrumentRepository(s).get_or_create(
                "CASC", asset_class=AssetClass.EQUITY
            )
            inst_id = inst.id
            TradeRepository(s).record(
                instrument_id=inst.id, side=TradeSide.BUY, quantity=1, price=1.0
            )
            PositionRepository(s).upsert(inst.id, quantity=1, avg_cost=1.0)
            ForecastRepository(s).record(
                instrument_id=inst.id,
                model=ForecastModel.GARCH,
                horizon_days=10,
                forecast_vol=0.2,
            )

        with database.session_scope() as s:
            inst = InstrumentRepository(s).get_by_symbol("CASC")
            assert inst is not None
            s.delete(inst)

        with database.session_scope() as s:
            assert PositionRepository(s).get_by_instrument(inst_id) is None
            assert TradeRepository(s).list_by_instrument(inst_id) == []
            assert ForecastRepository(s).history_for(inst_id) == []

    def test_foreign_key_violation_rejected(self, database: Database) -> None:
        with pytest.raises(IntegrityError), database.session_scope() as s:
            s.add(
                Trade(
                    instrument_id=999_999,
                    side=TradeSide.BUY,
                    quantity=1,
                    price=1.0,
                )
            )


# ---------------------------------------------------------------------------
# Transaction / concurrency behaviour
# ---------------------------------------------------------------------------


class TestTransactionIsolation:
    def test_uncommitted_writes_invisible_to_other_session(
        self, database: Database
    ) -> None:
        """An uncommitted insert in session A must not be visible to session B."""
        sa = database.session()
        sb = database.session()
        try:
            InstrumentRepository(sa).get_or_create(
                "ISO", asset_class=AssetClass.EQUITY
            )
            # No commit on sa yet. sb (a fresh session) should not see ISO.
            assert InstrumentRepository(sb).get_by_symbol("ISO") is None
            sa.commit()
            sb.close()

            sb = database.session()
            assert InstrumentRepository(sb).get_by_symbol("ISO") is not None
        finally:
            sa.close()
            sb.close()

    def test_explicit_rollback_drops_writes(self, database: Database) -> None:
        s = database.session()
        try:
            InstrumentRepository(s).get_or_create("RBK", asset_class=AssetClass.EQUITY)
            s.rollback()
        finally:
            s.close()

        with database.session_scope() as s:
            assert InstrumentRepository(s).get_by_symbol("RBK") is None

    def test_repository_rolls_back_on_flush_error(
        self, database: Database
    ) -> None:
        """A failed flush inside a repository must leave the session usable."""
        with database.session_scope() as s:
            InstrumentRepository(s).get_or_create(
                "FLUSH", asset_class=AssetClass.EQUITY
            )

        s = database.session()
        try:
            repo = InstrumentRepository(s)
            with pytest.raises(IntegrityError):
                # Duplicate symbol — flush in `add` will fail.
                repo.add(Instrument(symbol="FLUSH", asset_class=AssetClass.EQUITY))

            # After the rollback the session is reusable.
            repo.get_or_create("FLUSH2", asset_class=AssetClass.EQUITY)
            s.commit()
        finally:
            s.close()

        with database.session_scope() as s:
            assert InstrumentRepository(s).get_by_symbol("FLUSH2") is not None

    def test_concurrent_sessions_both_commit(self, database: Database) -> None:
        """Two independent sessions can each commit writes against the same DB.

        SQLite serialises writers (only one transaction can hold the
        write lock at a time), so the test commits ``sa`` before ``sb``
        starts its write. Both sessions remain live across the sequence
        — this proves the engine + session_factory hand out genuinely
        independent sessions, not aliases of a single one.
        """
        sa = database.session()
        sb = database.session()
        try:
            InstrumentRepository(sa).get_or_create(
                "CA", asset_class=AssetClass.EQUITY
            )
            sa.commit()
            InstrumentRepository(sb).get_or_create(
                "CB", asset_class=AssetClass.EQUITY
            )
            sb.commit()
            # sa is still usable for reads after sb's commit.
            symbols_seen_by_sa = {
                i.symbol for i in InstrumentRepository(sa).list_all()
            }
            assert {"CA", "CB"}.issubset(symbols_seen_by_sa)
        finally:
            sa.close()
            sb.close()
