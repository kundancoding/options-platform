"""Unit tests for :mod:`options_platform.data.yfinance_client`.

These tests do not hit the network. They monkeypatch ``yfinance.Ticker``
with a stub that returns canned values, exceptions, or empty frames so we
can exercise the canonical schema, retry behaviour, and error mapping in
isolation.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pandas as pd
import pytest
import requests

from options_platform.data import yfinance_client as yfc
from options_platform.data.yfinance_client import (
    HISTORY_COLUMNS,
    OPTION_CHAIN_COLUMNS,
    MarketDataError,
    RetryConfig,
    YFinanceClient,
)


# --- fakes --------------------------------------------------------------


class _FakeTicker:
    """Stub :class:`yfinance.Ticker` whose behaviour is per-test."""

    def __init__(
        self,
        history: pd.DataFrame | None = None,
        options: tuple[str, ...] = (),
        chain: SimpleNamespace | None = None,
        fast_info: Any | None = None,
        info: dict[str, Any] | None = None,
        raise_on_history: BaseException | None = None,
        raise_on_chain: BaseException | None = None,
    ) -> None:
        self._history = history
        self.options = options
        self._chain = chain
        self.fast_info = fast_info
        self.info = info or {}
        self._raise_history = raise_on_history
        self._raise_chain = raise_on_chain
        self.history_calls = 0
        self.chain_calls = 0

    def history(self, **kwargs: Any) -> pd.DataFrame:
        self.history_calls += 1
        if self._raise_history is not None:
            exc = self._raise_history
            # Only raise on first N attempts? The test sets behaviour by
            # swapping the ticker between calls; here we always raise.
            raise exc
        return self._history if self._history is not None else pd.DataFrame()

    def option_chain(self, expiration: str) -> SimpleNamespace:
        self.chain_calls += 1
        if self._raise_chain is not None:
            raise self._raise_chain
        if self._chain is None:
            raise ValueError(f"no chain for {expiration}")
        return self._chain


def _ohlcv_frame() -> pd.DataFrame:
    idx = pd.date_range("2026-01-02", periods=3, freq="B")
    return pd.DataFrame(
        {
            "Open": [100.0, 101.0, 102.0],
            "High": [101.5, 102.5, 103.5],
            "Low": [99.5, 100.5, 101.5],
            "Close": [101.0, 102.0, 103.0],
            "Volume": [1_000_000, 1_100_000, 950_000],
        },
        index=idx,
    )


def _chain_namespace() -> SimpleNamespace:
    calls = pd.DataFrame(
        {
            "contractSymbol": ["AAPL260619C00150000"],
            "strike": [150.0],
            "lastPrice": [5.25],
            "bid": [5.20],
            "ask": [5.30],
            "volume": [1234],
            "openInterest": [5678],
            "impliedVolatility": [0.32],
            "inTheMoney": [True],
        }
    )
    puts = pd.DataFrame(
        {
            "contractSymbol": ["AAPL260619P00150000"],
            "strike": [150.0],
            "lastPrice": [4.10],
            "bid": [4.05],
            "ask": [4.15],
            "volume": [800],
            "openInterest": [4321],
            "impliedVolatility": [0.30],
            "inTheMoney": [False],
        }
    )
    return SimpleNamespace(calls=calls, puts=puts)


# --- tests --------------------------------------------------------------


def test_get_price_returns_float(monkeypatch: pytest.MonkeyPatch) -> None:
    ticker = _FakeTicker(fast_info=SimpleNamespace(last_price=187.42))
    monkeypatch.setattr(yfc.yf, "Ticker", lambda _sym: ticker)
    client = YFinanceClient()
    assert client.get_price("aapl") == pytest.approx(187.42)


def test_get_price_falls_back_to_info(monkeypatch: pytest.MonkeyPatch) -> None:
    ticker = _FakeTicker(fast_info=None, info={"regularMarketPrice": 99.0})
    monkeypatch.setattr(yfc.yf, "Ticker", lambda _sym: ticker)
    client = YFinanceClient()
    assert client.get_price("MSFT") == 99.0


def test_get_price_invalid_ticker_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    ticker = _FakeTicker(fast_info=None, info={})
    monkeypatch.setattr(yfc.yf, "Ticker", lambda _sym: ticker)
    client = YFinanceClient()
    with pytest.raises(MarketDataError):
        client.get_price("FAKE")


def test_get_price_rejects_blank_symbol() -> None:
    client = YFinanceClient()
    with pytest.raises(MarketDataError):
        client.get_price("   ")


def test_get_expirations_returns_tuple(monkeypatch: pytest.MonkeyPatch) -> None:
    ticker = _FakeTicker(options=("2026-05-15", "2026-06-19"))
    monkeypatch.setattr(yfc.yf, "Ticker", lambda _sym: ticker)
    client = YFinanceClient()
    assert client.get_expirations("AAPL") == ("2026-05-15", "2026-06-19")


def test_get_expirations_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    ticker = _FakeTicker(options=())
    monkeypatch.setattr(yfc.yf, "Ticker", lambda _sym: ticker)
    client = YFinanceClient()
    assert client.get_expirations("NOOPT") == ()


def test_get_option_chain_canonical_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    ticker = _FakeTicker(chain=_chain_namespace())
    monkeypatch.setattr(yfc.yf, "Ticker", lambda _sym: ticker)
    client = YFinanceClient()
    chain = client.get_option_chain("AAPL", "2026-06-19")
    assert list(chain.columns) == list(OPTION_CHAIN_COLUMNS)
    assert set(chain["option_type"]) == {"call", "put"}
    assert (chain["expiration"] == "2026-06-19").all()


def test_get_option_chain_empty_returns_empty_frame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    empty = SimpleNamespace(calls=pd.DataFrame(), puts=pd.DataFrame())
    ticker = _FakeTicker(chain=empty)
    monkeypatch.setattr(yfc.yf, "Ticker", lambda _sym: ticker)
    client = YFinanceClient()
    chain = client.get_option_chain("AAPL", "2026-06-19")
    assert chain.empty
    assert list(chain.columns) == list(OPTION_CHAIN_COLUMNS)


def test_get_option_chain_unknown_expiration_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ticker = _FakeTicker(chain=None)  # raises ValueError on call
    monkeypatch.setattr(yfc.yf, "Ticker", lambda _sym: ticker)
    client = YFinanceClient()
    with pytest.raises(MarketDataError):
        client.get_option_chain("AAPL", "1999-01-01")


def test_get_history_returns_canonical_frame(monkeypatch: pytest.MonkeyPatch) -> None:
    ticker = _FakeTicker(history=_ohlcv_frame())
    monkeypatch.setattr(yfc.yf, "Ticker", lambda _sym: ticker)
    client = YFinanceClient()
    df = client.get_history("AAPL", period="5d")
    assert list(df.columns) == list(HISTORY_COLUMNS)
    assert df.index.name == "date"
    assert len(df) == 3
    assert df["close"].iloc[-1] == 103.0


def test_get_history_empty_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    ticker = _FakeTicker(history=pd.DataFrame())
    monkeypatch.setattr(yfc.yf, "Ticker", lambda _sym: ticker)
    client = YFinanceClient()
    with pytest.raises(MarketDataError):
        client.get_history("AAPL", period="5d")


def test_retry_succeeds_after_transient_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A retryable exception on attempt 1 should be retried and succeed."""
    good = _FakeTicker(history=_ohlcv_frame())
    bad = _FakeTicker(raise_on_history=requests.exceptions.ConnectionError("boom"))
    sequence = [bad, good]
    monkeypatch.setattr(yfc.yf, "Ticker", lambda _sym: sequence.pop(0))
    sleeps: list[float] = []
    client = YFinanceClient(
        retry=RetryConfig(max_attempts=3, initial_backoff_sec=0.0),
        sleep=lambda s: sleeps.append(s),
    )
    # Use a fresh client so the per-symbol ticker cache picks up `bad` first
    # then `good`. We bypass the cache by clearing it between attempts via
    # the monkeypatched factory: each call to `yf.Ticker` pops from `sequence`.
    client._tickers.clear()
    # Trigger the first call -> uses `bad` -> raises -> retry -> `good`.
    # Because YFinanceClient caches the ticker, we must clear after the
    # first failure. Simulate that by patching `_ticker` to always rebuild.
    monkeypatch.setattr(
        client, "_ticker", lambda sym: yfc.yf.Ticker(sym)  # type: ignore[arg-type]
    )
    df = client.get_history("AAPL", period="5d")
    assert len(df) == 3
    assert len(sleeps) == 1  # one backoff between two attempts


def test_retry_exhausts_then_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    bad = _FakeTicker(raise_on_history=requests.exceptions.Timeout("slow"))
    monkeypatch.setattr(yfc.yf, "Ticker", lambda _sym: bad)
    sleeps: list[float] = []
    client = YFinanceClient(
        retry=RetryConfig(max_attempts=3, initial_backoff_sec=0.0),
        sleep=lambda s: sleeps.append(s),
    )
    with pytest.raises(MarketDataError):
        client.get_history("AAPL", period="5d")
    # 3 attempts → 2 sleeps between them.
    assert len(sleeps) == 2


def test_marketdataerror_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    """Deterministic failures (bad ticker, empty data) bypass retry."""
    ticker = _FakeTicker(history=pd.DataFrame())  # empty -> MarketDataError
    monkeypatch.setattr(yfc.yf, "Ticker", lambda _sym: ticker)
    client = YFinanceClient(retry=RetryConfig(max_attempts=5, initial_backoff_sec=0.0))
    with pytest.raises(MarketDataError):
        client.get_history("AAPL", period="5d")
    assert ticker.history_calls == 1  # not retried
