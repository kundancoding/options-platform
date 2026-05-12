"""Thin wrapper around the :mod:`yfinance` library.

This module isolates every call into Yahoo Finance behind a small,
testable surface. Responsibilities:

* Construct and reuse :class:`yfinance.Ticker` instances.
* Apply retry-with-exponential-backoff to every network call so transient
  errors (rate limits, DNS hiccups, 5xx responses) do not bubble up.
* Convert raw yfinance return values into typed pandas DataFrames with a
  stable schema, regardless of upstream column-name drift.
* Surface a consistent failure mode: methods either return a
  well-formed DataFrame/dict or raise :class:`MarketDataError`.

The higher-level :mod:`options_platform.data.data_fetcher` module composes
this client with the local cache.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd
import requests
import yfinance as yf

from options_platform.utils.logging import get_logger

logger = get_logger(__name__)


class MarketDataError(RuntimeError):
    """Raised when market data cannot be retrieved after retries."""


HISTORY_COLUMNS: tuple[str, ...] = ("open", "high", "low", "close", "volume")
"""Canonical OHLCV column order used everywhere downstream."""

OPTION_CHAIN_COLUMNS: tuple[str, ...] = (
    "contract_symbol",
    "strike",
    "last_price",
    "bid",
    "ask",
    "volume",
    "open_interest",
    "implied_volatility",
    "in_the_money",
    "expiration",
    "option_type",
)
"""Canonical option-chain column order (calls + puts concatenated)."""

# Errors worth retrying — network/HTTP transient classes only.
_RETRYABLE_EXCEPTIONS: tuple[type[BaseException], ...] = (
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
    requests.exceptions.ChunkedEncodingError,
    requests.exceptions.HTTPError,
)


@dataclass
class RetryConfig:
    """Retry policy for outbound calls.

    Attributes:
        max_attempts: Total tries including the first. ``1`` disables retry.
        initial_backoff_sec: Sleep before the second attempt.
        backoff_multiplier: Each subsequent sleep is multiplied by this.
        max_backoff_sec: Cap on the sleep between attempts.
    """

    max_attempts: int = 3
    initial_backoff_sec: float = 0.5
    backoff_multiplier: float = 2.0
    max_backoff_sec: float = 8.0


@dataclass
class YFinanceClient:
    """Network-facing yfinance adapter.

    The client is intentionally stateless apart from a small in-process
    :class:`yfinance.Ticker` cache (``_tickers``) so repeated lookups for the
    same symbol within one process do not re-instantiate the underlying
    HTTP session.

    Attributes:
        retry: Retry policy applied to each public method.
        sleep: Indirection over :func:`time.sleep` so tests can inject a
            no-op or fake clock.
    """

    retry: RetryConfig = field(default_factory=RetryConfig)
    sleep: Any = time.sleep
    _tickers: dict[str, yf.Ticker] = field(default_factory=dict, init=False, repr=False)

    # --- public API ---------------------------------------------------

    def get_price(self, symbol: str) -> float:
        """Return the most recent trade price for ``symbol``.

        Args:
            symbol: Equity / ETF ticker (e.g. ``"AAPL"``).

        Returns:
            Latest available price as a ``float``.

        Raises:
            MarketDataError: The symbol is unknown or no price could be
                retrieved after the configured retries.
        """
        symbol = self._normalize_symbol(symbol)

        def _call() -> float:
            ticker = self._ticker(symbol)
            price = self._extract_price(ticker)
            if price is None:
                raise MarketDataError(f"No price available for {symbol!r}")
            return float(price)

        return self._with_retry(f"get_price({symbol})", _call)

    def get_expirations(self, symbol: str) -> tuple[str, ...]:
        """Return all available option expirations for ``symbol``.

        Args:
            symbol: Underlying ticker.

        Returns:
            Tuple of ``YYYY-MM-DD`` strings, sorted ascending. Empty tuple
            if the underlying has no listed options.

        Raises:
            MarketDataError: Network failure exhausted the retry budget.
        """
        symbol = self._normalize_symbol(symbol)

        def _call() -> tuple[str, ...]:
            ticker = self._ticker(symbol)
            options = getattr(ticker, "options", None) or ()
            return tuple(options)

        return self._with_retry(f"get_expirations({symbol})", _call)

    def get_option_chain(self, symbol: str, expiration: str) -> pd.DataFrame:
        """Return the option chain for ``symbol`` at ``expiration``.

        Calls and puts are concatenated into a single DataFrame with an
        ``option_type`` column (``"call"`` or ``"put"``) and the canonical
        schema described by :data:`OPTION_CHAIN_COLUMNS`.

        Args:
            symbol: Underlying ticker.
            expiration: Expiration as ``YYYY-MM-DD``.

        Returns:
            Typed DataFrame. Empty (zero-row) DataFrame with the canonical
            schema if the chain is empty.

        Raises:
            MarketDataError: Underlying does not list this expiration, or
                retries were exhausted.
        """
        symbol = self._normalize_symbol(symbol)

        def _call() -> pd.DataFrame:
            ticker = self._ticker(symbol)
            try:
                chain = ticker.option_chain(expiration)
            except (ValueError, KeyError, AttributeError) as exc:
                raise MarketDataError(
                    f"No option chain for {symbol!r} @ {expiration!r}: {exc}"
                ) from exc
            calls = getattr(chain, "calls", None)
            puts = getattr(chain, "puts", None)
            return self._normalize_chain(calls, puts, expiration)

        return self._with_retry(
            f"get_option_chain({symbol}, {expiration})", _call
        )

    def get_history(
        self,
        symbol: str,
        start: datetime | str | None = None,
        end: datetime | str | None = None,
        period: str | None = None,
        interval: str = "1d",
    ) -> pd.DataFrame:
        """Return historical OHLCV bars for ``symbol``.

        Either ``period`` (e.g. ``"1y"``) or an explicit ``start`` / ``end``
        window can be supplied. ``period`` wins if both are provided.

        Args:
            symbol: Equity / ETF ticker.
            start: Inclusive start date (datetime or ``YYYY-MM-DD`` string).
            end: Inclusive end date (datetime or ``YYYY-MM-DD`` string).
            period: yfinance shorthand (``"1d"``, ``"5d"``, ``"1mo"``,
                ``"1y"``, ``"max"`` …). If set, ``start`` and ``end`` are
                ignored.
            interval: Bar size (``"1d"``, ``"1h"``, ``"1m"`` …).

        Returns:
            DataFrame with a ``DatetimeIndex`` named ``date`` and the
            canonical columns from :data:`HISTORY_COLUMNS`.

        Raises:
            MarketDataError: Unknown ticker, empty response, or retries
                exhausted.
        """
        symbol = self._normalize_symbol(symbol)

        def _call() -> pd.DataFrame:
            ticker = self._ticker(symbol)
            kwargs: dict[str, Any] = {"interval": interval, "auto_adjust": False}
            if period:
                kwargs["period"] = period
            else:
                if start is not None:
                    kwargs["start"] = start
                if end is not None:
                    kwargs["end"] = end
            raw = ticker.history(**kwargs)
            if raw is None or raw.empty:
                raise MarketDataError(
                    f"No history for {symbol!r} (params={kwargs})"
                )
            return self._normalize_history(raw)

        return self._with_retry(f"get_history({symbol})", _call)

    # --- internals ----------------------------------------------------

    def _ticker(self, symbol: str) -> yf.Ticker:
        """Return a cached :class:`yfinance.Ticker` for ``symbol``."""
        ticker = self._tickers.get(symbol)
        if ticker is None:
            ticker = yf.Ticker(symbol)
            self._tickers[symbol] = ticker
        return ticker

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        """Validate and canonicalize a ticker string."""
        if not isinstance(symbol, str) or not symbol.strip():
            raise MarketDataError(f"Invalid ticker: {symbol!r}")
        return symbol.strip().upper()

    @staticmethod
    def _extract_price(ticker: yf.Ticker) -> float | None:
        """Pull the latest price from ``ticker`` using fast_info / info."""
        fast = getattr(ticker, "fast_info", None)
        if fast is not None:
            for key in ("last_price", "lastPrice", "regular_market_price"):
                value = _safe_get(fast, key)
                if value is not None:
                    return float(value)
        info = getattr(ticker, "info", None) or {}
        for key in ("regularMarketPrice", "currentPrice", "previousClose"):
            value = info.get(key) if isinstance(info, dict) else None
            if value is not None:
                return float(value)
        return None

    @staticmethod
    def _normalize_history(raw: pd.DataFrame) -> pd.DataFrame:
        """Coerce a yfinance history frame to the canonical schema."""
        df = raw.copy()
        df.columns = [str(c).lower().replace(" ", "_") for c in df.columns]
        missing = [c for c in HISTORY_COLUMNS if c not in df.columns]
        if missing:
            raise MarketDataError(
                f"History frame missing columns {missing}: got {list(df.columns)}"
            )
        df = df.loc[:, list(HISTORY_COLUMNS)].astype(
            {
                "open": "float64",
                "high": "float64",
                "low": "float64",
                "close": "float64",
                "volume": "int64",
            },
            errors="ignore",
        )
        df.index = pd.to_datetime(df.index).tz_localize(None)
        df.index.name = "date"
        return df

    @staticmethod
    def _normalize_chain(
        calls: pd.DataFrame | None,
        puts: pd.DataFrame | None,
        expiration: str,
    ) -> pd.DataFrame:
        """Concatenate calls and puts into the canonical chain schema."""
        frames: list[pd.DataFrame] = []
        for side, df in (("call", calls), ("put", puts)):
            if df is None or df.empty:
                continue
            tagged = df.copy()
            tagged.columns = [str(c).lower() for c in tagged.columns]
            tagged = tagged.rename(
                columns={
                    "contractsymbol": "contract_symbol",
                    "lastprice": "last_price",
                    "openinterest": "open_interest",
                    "impliedvolatility": "implied_volatility",
                    "inthemoney": "in_the_money",
                }
            )
            tagged["expiration"] = expiration
            tagged["option_type"] = side
            frames.append(tagged)

        if not frames:
            empty = pd.DataFrame(columns=list(OPTION_CHAIN_COLUMNS))
            return empty

        merged = pd.concat(frames, ignore_index=True, sort=False)
        for col in OPTION_CHAIN_COLUMNS:
            if col not in merged.columns:
                merged[col] = pd.NA
        return merged.loc[:, list(OPTION_CHAIN_COLUMNS)]

    def _with_retry(self, label: str, fn: Any) -> Any:
        """Invoke ``fn`` under the configured retry policy."""
        attempts = max(1, self.retry.max_attempts)
        backoff = self.retry.initial_backoff_sec
        last_exc: BaseException | None = None
        for attempt in range(1, attempts + 1):
            try:
                return fn()
            except MarketDataError:
                # Don't retry deterministic failures (e.g. bad ticker).
                raise
            except _RETRYABLE_EXCEPTIONS as exc:
                last_exc = exc
                logger.warning(
                    "{label} attempt {attempt}/{attempts} failed: {exc}",
                    label=label,
                    attempt=attempt,
                    attempts=attempts,
                    exc=exc,
                )
                if attempt == attempts:
                    break
                self.sleep(min(backoff, self.retry.max_backoff_sec))
                backoff *= self.retry.backoff_multiplier
            except Exception as exc:  # noqa: BLE001 - convert to typed error
                logger.exception("{label} failed with non-retryable error", label=label)
                raise MarketDataError(f"{label} failed: {exc}") from exc
        raise MarketDataError(
            f"{label} failed after {attempts} attempts: {last_exc}"
        ) from last_exc


def _safe_get(obj: Any, key: str) -> Any:
    """Best-effort attribute / mapping read used for :attr:`fast_info`."""
    try:
        if isinstance(obj, dict):
            return obj.get(key)
        if hasattr(obj, key):
            return getattr(obj, key)
        try:
            return obj[key]  # type: ignore[index]
        except (KeyError, TypeError, IndexError):
            return None
    except Exception:  # noqa: BLE001 - fast_info is notoriously flaky
        return None
