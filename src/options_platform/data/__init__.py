"""Persistence and market-data layer.

- :mod:`options_platform.data.database`  — SQLite connection / engine factory.
- :mod:`options_platform.data.models`    — SQLAlchemy ORM models.
- :mod:`options_platform.data.repository`— repository pattern over models.
- :mod:`options_platform.data.market_data` — high-level market-data facade.
- :mod:`options_platform.data.providers` — concrete data-source adapters.
"""

from options_platform.data.database import get_engine, get_session
from options_platform.data.market_data import MarketDataService
from options_platform.data.repository import (
    OrderRepository,
    PortfolioRepository,
    PositionRepository,
    QuoteRepository,
)

__all__ = [
    "get_engine",
    "get_session",
    "MarketDataService",
    "OrderRepository",
    "PortfolioRepository",
    "PositionRepository",
    "QuoteRepository",
]
