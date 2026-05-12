"""Unit tests for :mod:`options_platform.data.data_fetcher`."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from options_platform.data.cache_manager import CacheManager
from options_platform.data.data_fetcher import DataFetcher
from options_platform.data.yfinance_client import (
    HISTORY_COLUMNS,
    OPTION_CHAIN_COLUMNS,
    MarketDataError,
)


class _StubClient:
    """In-memory stub mirroring :class:`YFinanceClient`'s public surface."""

    def __init__(self) -> None:
        self.price_calls = 0
        self.history_calls = 0
        self.chain_calls = 0
        self.expirations_calls = 0
        self.price_value: float | BaseException = 100.0
        self.history_value: pd.DataFrame | BaseException = _sample_history()
        self.chain_value: pd.DataFrame | BaseException = _sample_chain(
            "2026-06-19"
        )
        self.expirations_value: tuple[str, ...] | BaseException = (
            "2026-06-19",
            "2026-07-17",
        )

    def get_price(self, symbol: str) -> float:
        self.price_calls += 1
        if isinstance(self.price_value, BaseException):
            raise self.price_value
        return float(self.price_value)

    def get_expirations(self, symbol: str) -> tuple[str, ...]:
        self.expirations_calls += 1
        if isinstance(self.expirations_value, BaseException):
            raise self.expirations_value
        return self.expirations_value

    def get_option_chain(self, symbol: str, expiration: str) -> pd.DataFrame:
        self.chain_calls += 1
        if isinstance(self.chain_value, BaseException):
            raise self.chain_value
        return self.chain_value

    def get_history(
        self,
        symbol: str,
        start: Any = None,
        end: Any = None,
        period: str | None = None,
        interval: str = "1d",
    ) -> pd.DataFrame:
        self.history_calls += 1
        if isinstance(self.history_value, BaseException):
            raise self.history_value
        return self.history_value


def _sample_history() -> pd.DataFrame:
    idx = pd.DatetimeIndex(
        pd.to_datetime(["2026-01-02", "2026-01-03", "2026-01-04"]), name="date"
    )
    return pd.DataFrame(
        {
            "open": [100.0, 101.0, 102.0],
            "high": [101.0, 102.0, 103.0],
            "low": [99.0, 100.0, 101.0],
            "close": [100.5, 101.5, 102.5],
            "volume": [1_000_000, 1_100_000, 950_000],
        },
        index=idx,
    )


def _sample_chain(expiration: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "contract_symbol": ["AAPL_C"],
            "strike": [150.0],
            "last_price": [5.0],
            "bid": [4.9],
            "ask": [5.1],
            "volume": [100],
            "open_interest": [200],
            "implied_volatility": [0.3],
            "in_the_money": [True],
            "expiration": [expiration],
            "option_type": ["call"],
        }
    )


@pytest.fixture
def fetcher(tmp_path: Path) -> tuple[DataFetcher, _StubClient]:
    stub = _StubClient()
    cache = CacheManager(cache_dir=tmp_path, default_ttl_sec=60)
    f = DataFetcher(client=stub, cache=cache)  # type: ignore[arg-type]
    return f, stub


# --- prices ----------------------------------------------------------


def test_get_current_price_valid(fetcher: tuple[DataFetcher, _StubClient]) -> None:
    f, stub = fetcher
    stub.price_value = 142.5
    assert f.get_current_price("AAPL") == 142.5


def test_get_current_price_invalid_returns_none(
    fetcher: tuple[DataFetcher, _StubClient],
) -> None:
    f, stub = fetcher
    stub.price_value = MarketDataError("unknown")
    assert f.get_current_price("FAKE") is None


def test_get_current_price_cache_hit(
    fetcher: tuple[DataFetcher, _StubClient],
) -> None:
    f, stub = fetcher
    stub.price_value = 50.0
    first = f.get_current_price("AAPL")
    second = f.get_current_price("AAPL")
    assert first == second == 50.0
    assert stub.price_calls == 1  # second call was a cache hit


def test_get_current_price_cache_miss_then_hit(
    fetcher: tuple[DataFetcher, _StubClient],
) -> None:
    f, stub = fetcher
    stub.price_value = 75.0
    assert f.get_current_price("AAPL") == 75.0
    assert stub.price_calls == 1
    # Different symbol → miss → upstream called again.
    stub.price_value = 80.0
    assert f.get_current_price("MSFT") == 80.0
    assert stub.price_calls == 2


# --- expirations -----------------------------------------------------


def test_get_expirations_valid(fetcher: tuple[DataFetcher, _StubClient]) -> None:
    f, stub = fetcher
    assert f.get_expirations("AAPL") == ["2026-06-19", "2026-07-17"]


def test_get_expirations_invalid_returns_empty(
    fetcher: tuple[DataFetcher, _StubClient],
) -> None:
    f, stub = fetcher
    stub.expirations_value = MarketDataError("boom")
    assert f.get_expirations("FAKE") == []


# --- option chain ----------------------------------------------------


def test_get_option_chain_defaults_to_first_expiration(
    fetcher: tuple[DataFetcher, _StubClient],
) -> None:
    f, stub = fetcher
    chain = f.get_option_chain("AAPL")
    assert not chain.empty
    assert list(chain.columns) == list(OPTION_CHAIN_COLUMNS)
    assert stub.expirations_calls == 1
    assert stub.chain_calls == 1


def test_get_option_chain_empty_when_no_expirations(
    fetcher: tuple[DataFetcher, _StubClient],
) -> None:
    f, stub = fetcher
    stub.expirations_value = ()
    chain = f.get_option_chain("NOOPT")
    assert chain.empty
    assert list(chain.columns) == list(OPTION_CHAIN_COLUMNS)
    assert stub.chain_calls == 0  # short-circuited


def test_get_option_chain_failure_returns_empty(
    fetcher: tuple[DataFetcher, _StubClient],
) -> None:
    f, stub = fetcher
    stub.chain_value = MarketDataError("upstream")
    chain = f.get_option_chain("AAPL", expiration="2026-06-19")
    assert chain.empty
    assert list(chain.columns) == list(OPTION_CHAIN_COLUMNS)


def test_get_option_chain_cache_hit(
    fetcher: tuple[DataFetcher, _StubClient],
) -> None:
    f, stub = fetcher
    f.get_option_chain("AAPL", expiration="2026-06-19")
    f.get_option_chain("AAPL", expiration="2026-06-19")
    assert stub.chain_calls == 1


# --- history ---------------------------------------------------------


def test_get_historical_data_valid(
    fetcher: tuple[DataFetcher, _StubClient],
) -> None:
    f, _ = fetcher
    df = f.get_historical_data("AAPL", period="1mo")
    assert list(df.columns) == list(HISTORY_COLUMNS)
    assert len(df) == 3


def test_get_historical_data_failure_returns_empty(
    fetcher: tuple[DataFetcher, _StubClient],
) -> None:
    f, stub = fetcher
    stub.history_value = MarketDataError("nope")
    df = f.get_historical_data("FAKE", period="1mo")
    assert df.empty
    assert list(df.columns) == list(HISTORY_COLUMNS)


def test_get_historical_data_cache_hit(
    fetcher: tuple[DataFetcher, _StubClient],
) -> None:
    f, stub = fetcher
    f.get_historical_data("AAPL", period="1mo")
    f.get_historical_data("AAPL", period="1mo")
    assert stub.history_calls == 1


def test_get_historical_data_distinct_args_miss(
    fetcher: tuple[DataFetcher, _StubClient],
) -> None:
    f, stub = fetcher
    f.get_historical_data("AAPL", period="1mo")
    f.get_historical_data("AAPL", period="3mo")
    assert stub.history_calls == 2


# --- cache controls --------------------------------------------------


def test_invalidate_forces_refresh(
    fetcher: tuple[DataFetcher, _StubClient],
) -> None:
    f, stub = fetcher
    stub.price_value = 10.0
    f.get_current_price("AAPL")
    f.invalidate("AAPL")
    stub.price_value = 11.0
    assert f.get_current_price("AAPL") == 11.0
    assert stub.price_calls == 2


def test_disabled_cache_always_refetches(tmp_path: Path) -> None:
    stub = _StubClient()
    cache = CacheManager(cache_dir=tmp_path, enabled=False)
    f = DataFetcher(client=stub, cache=cache)  # type: ignore[arg-type]
    f.get_current_price("AAPL")
    f.get_current_price("AAPL")
    assert stub.price_calls == 2
