"""High-level normalized market-data facade."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from options_platform.data.providers.base import MarketDataProvider


@dataclass
class MarketDataService:
    """Thin provider facade with stable history and quote schemas."""

    provider: MarketDataProvider

    def history(self, symbol: str, start: datetime, end: datetime) -> pd.DataFrame:
        frame = self.provider.history(symbol.strip().upper(), start, end).copy()
        frame.columns = [str(column).lower() for column in frame.columns]
        required = ["open", "high", "low", "close", "volume"]
        missing = set(required).difference(frame.columns)
        if missing:
            raise ValueError(f"history is missing columns: {sorted(missing)}")
        return frame.loc[:, required]

    def option_chain(self, underlying: str, expiry: datetime | None = None) -> pd.DataFrame:
        return self.provider.option_chain(underlying.strip().upper(), expiry)

    def quote(self, symbol: str) -> dict[str, float]:
        quote = self.provider.quote(symbol.strip().upper())
        return {key: float(quote.get(key, 0.0)) for key in ("bid", "ask", "last", "volume")}
