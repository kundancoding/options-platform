"""Abstract market-data provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

import pandas as pd


class MarketDataProvider(ABC):
    """Minimum surface every concrete provider must implement."""

    @abstractmethod
    def history(self, symbol: str, start: datetime, end: datetime) -> pd.DataFrame:
        """Return daily OHLCV bars indexed by date."""

    @abstractmethod
    def option_chain(self, underlying: str, expiry: datetime | None = None) -> pd.DataFrame:
        """Return the option chain in a normalized schema."""

    @abstractmethod
    def quote(self, symbol: str) -> dict[str, float]:
        """Return top-of-book quote: ``{"bid", "ask", "last", "volume"}``."""
