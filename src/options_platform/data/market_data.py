"""High-level market-data service.

Wraps the configured provider (yfinance by default) and caches recent
responses in the local SQLite store via the repositories.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from options_platform.data.providers.base import MarketDataProvider


@dataclass
class MarketDataService:
    """Facade combining a provider and the local quote cache."""

    provider: MarketDataProvider

    def history(self, symbol: str, start: datetime, end: datetime) -> pd.DataFrame:
        """Return OHLCV history for ``symbol`` between ``start`` and ``end``."""
        # TODO: check cache first; fall back to provider.history; persist new rows.
        raise NotImplementedError

    def option_chain(self, underlying: str, expiry: datetime | None = None) -> pd.DataFrame:
        """Return the option chain (optionally filtered to a single expiry)."""
        # TODO: provider.option_chain(...) → normalized DataFrame schema.
        raise NotImplementedError

    def quote(self, symbol: str) -> dict[str, float]:
        """Return the latest top-of-book quote for ``symbol``."""
        # TODO: provider.quote(symbol) → {"bid", "ask", "last", "volume"}.
        raise NotImplementedError
