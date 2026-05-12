"""High-level market-data facade.

:class:`DataFetcher` is the single object the rest of the platform talks
to when it needs prices, option chains, expirations, or historical bars.
It composes the low-level :class:`~options_platform.data.yfinance_client.YFinanceClient`
with the local
:class:`~options_platform.data.cache_manager.CacheManager` and adds:

* Cache-first reads with per-method TTL overrides.
* Graceful failure mapped to ``None`` / empty DataFrame so callers can
  render a UI rather than a stack trace.
* Stable, typed pandas outputs (see ``HISTORY_COLUMNS`` /
  ``OPTION_CHAIN_COLUMNS`` re-exported from :mod:`.yfinance_client`).

Typical use::

    fetcher = DataFetcher()
    spot = fetcher.get_current_price("AAPL")
    chain = fetcher.get_option_chain("AAPL", expiration="2026-06-19")
    bars = fetcher.get_historical_data("AAPL", period="1y")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd

from options_platform.data.cache_manager import CacheManager
from options_platform.data.yfinance_client import (
    HISTORY_COLUMNS,
    OPTION_CHAIN_COLUMNS,
    MarketDataError,
    YFinanceClient,
)
from options_platform.utils.logging import get_logger

logger = get_logger(__name__)


# Per-call-type defaults (seconds). Tunable via DataFetcher arguments.
_DEFAULT_PRICE_TTL = 60.0
_DEFAULT_EXPIRATIONS_TTL = 60 * 60.0
_DEFAULT_CHAIN_TTL = 5 * 60.0
_DEFAULT_HISTORY_TTL = 24 * 60 * 60.0


@dataclass
class DataFetcher:
    """Cached, fault-tolerant market-data accessor.

    Attributes:
        client: Low-level yfinance adapter. A default instance is created
            if none is supplied.
        cache: Disk cache. A default instance is created if none is
            supplied. Pass ``CacheManager(enabled=False)`` to bypass.
        price_ttl_sec: TTL for :meth:`get_current_price`.
        expirations_ttl_sec: TTL for :meth:`get_expirations`.
        chain_ttl_sec: TTL for :meth:`get_option_chain`.
        history_ttl_sec: TTL for :meth:`get_historical_data`.
    """

    client: YFinanceClient = field(default_factory=YFinanceClient)
    cache: CacheManager = field(default_factory=CacheManager)
    price_ttl_sec: float = _DEFAULT_PRICE_TTL
    expirations_ttl_sec: float = _DEFAULT_EXPIRATIONS_TTL
    chain_ttl_sec: float = _DEFAULT_CHAIN_TTL
    history_ttl_sec: float = _DEFAULT_HISTORY_TTL

    # --- prices -------------------------------------------------------

    def get_current_price(self, symbol: str) -> float | None:
        """Return the latest price for ``symbol`` or ``None`` on failure.

        Args:
            symbol: Equity / ETF ticker.

        Returns:
            Last trade price, or ``None`` if the ticker is unknown or
            the upstream call failed after retries.
        """
        symbol = symbol.strip().upper()
        key = ("price", symbol)
        cached = self.cache.get(key)
        if cached is not None:
            logger.debug("price cache hit for {sym}", sym=symbol)
            return float(cached)
        try:
            price = self.client.get_price(symbol)
        except MarketDataError as exc:
            logger.warning("get_current_price({sym}) failed: {exc}",
                           sym=symbol, exc=exc)
            return None
        self.cache.set(key, price, ttl_sec=self.price_ttl_sec)
        return price

    # --- option chain -------------------------------------------------

    def get_expirations(self, symbol: str) -> list[str]:
        """Return all listed option expirations for ``symbol``.

        Args:
            symbol: Underlying ticker.

        Returns:
            List of ``YYYY-MM-DD`` strings. Empty list when the
            underlying has no listed options or the call failed.
        """
        symbol = symbol.strip().upper()
        key = ("expirations", symbol)
        cached = self.cache.get(key)
        if cached is not None:
            return list(cached)
        try:
            exps = self.client.get_expirations(symbol)
        except MarketDataError as exc:
            logger.warning("get_expirations({sym}) failed: {exc}",
                           sym=symbol, exc=exc)
            return []
        result = list(exps)
        self.cache.set(key, result, ttl_sec=self.expirations_ttl_sec)
        return result

    def get_option_chain(
        self,
        symbol: str,
        expiration: str | None = None,
    ) -> pd.DataFrame:
        """Return the option chain DataFrame.

        Args:
            symbol: Underlying ticker.
            expiration: Specific ``YYYY-MM-DD`` expiration. When omitted,
                the nearest available expiration is used.

        Returns:
            DataFrame with the canonical schema (see
            :data:`~options_platform.data.yfinance_client.OPTION_CHAIN_COLUMNS`).
            Returns an empty DataFrame with that schema on failure or
            when no chain is available.
        """
        symbol = symbol.strip().upper()

        if expiration is None:
            exps = self.get_expirations(symbol)
            if not exps:
                return _empty_chain()
            expiration = exps[0]

        key = ("option_chain", symbol, expiration)
        cached = self.cache.get(key)
        if isinstance(cached, pd.DataFrame):
            return cached

        try:
            chain = self.client.get_option_chain(symbol, expiration)
        except MarketDataError as exc:
            logger.warning("get_option_chain({sym}, {exp}) failed: {exc}",
                           sym=symbol, exp=expiration, exc=exc)
            return _empty_chain()

        self.cache.set(key, chain, ttl_sec=self.chain_ttl_sec)
        return chain

    # --- history ------------------------------------------------------

    def get_historical_data(
        self,
        symbol: str,
        start: datetime | str | None = None,
        end: datetime | str | None = None,
        period: str | None = None,
        interval: str = "1d",
    ) -> pd.DataFrame:
        """Return OHLCV bars for ``symbol``.

        Either ``period`` (e.g. ``"1y"``) or an explicit ``start`` / ``end``
        window must be provided.

        Args:
            symbol: Equity / ETF ticker.
            start: Inclusive start date.
            end: Inclusive end date.
            period: yfinance shorthand. Overrides ``start``/``end`` if set.
            interval: Bar size (default ``"1d"``).

        Returns:
            DataFrame indexed by date with canonical columns from
            :data:`~options_platform.data.yfinance_client.HISTORY_COLUMNS`.
            Returns an empty DataFrame with that schema on failure.
        """
        symbol = symbol.strip().upper()
        key = (
            "history",
            symbol,
            _date_key(start),
            _date_key(end),
            period,
            interval,
        )
        cached = self.cache.get(key)
        if isinstance(cached, pd.DataFrame):
            return cached

        try:
            df = self.client.get_history(
                symbol, start=start, end=end, period=period, interval=interval
            )
        except MarketDataError as exc:
            logger.warning("get_historical_data({sym}) failed: {exc}",
                           sym=symbol, exc=exc)
            return _empty_history()

        self.cache.set(key, df, ttl_sec=self.history_ttl_sec)
        return df

    # --- cache controls ----------------------------------------------

    def invalidate(self, symbol: str | None = None) -> None:
        """Drop cached entries.

        Args:
            symbol: If given, all cache entries are cleared (the cache is
                content-addressed by hash, so we cannot selectively drop
                just one symbol without an index). If ``None``, equivalent
                to :meth:`CacheManager.clear`.
        """
        # Both paths perform a full clear; ``symbol`` is accepted for API
        # symmetry with callers that pass a specific ticker.
        _ = symbol
        self.cache.clear()


# --- helpers ----------------------------------------------------------


def _empty_history() -> pd.DataFrame:
    """Empty history DataFrame with the canonical schema and dtypes."""
    df = pd.DataFrame({col: pd.Series(dtype="float64") for col in HISTORY_COLUMNS})
    df["volume"] = df["volume"].astype("int64")
    df.index = pd.DatetimeIndex([], name="date")
    return df


def _empty_chain() -> pd.DataFrame:
    """Empty option-chain DataFrame with the canonical schema."""
    return pd.DataFrame(columns=list(OPTION_CHAIN_COLUMNS))


def _date_key(value: Any) -> str | None:
    """Render a date/datetime/string in a stable form for cache keys."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    return str(value)
