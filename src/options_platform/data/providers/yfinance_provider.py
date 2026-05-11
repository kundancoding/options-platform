"""yfinance-backed implementation of :class:`MarketDataProvider`."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from options_platform.data.providers.base import MarketDataProvider


class YFinanceProvider(MarketDataProvider):
    """Fetch quotes / chains via the unofficial Yahoo Finance API."""

    def history(self, symbol: str, start: datetime, end: datetime) -> pd.DataFrame:
        # TODO: yfinance.Ticker(symbol).history(start=..., end=...)
        # then standardize columns to ["open","high","low","close","volume"].
        raise NotImplementedError

    def option_chain(self, underlying: str, expiry: datetime | None = None) -> pd.DataFrame:
        # TODO: yf.Ticker(underlying).option_chain(date) → concat calls/puts.
        raise NotImplementedError

    def quote(self, symbol: str) -> dict[str, float]:
        # TODO: yf.Ticker(symbol).fast_info → {"bid","ask","last","volume"}.
        raise NotImplementedError
