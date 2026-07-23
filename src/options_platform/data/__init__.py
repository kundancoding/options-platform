"""Persistence and market-data layer.

- :mod:`options_platform.data.database`   — engine + session factory.
- :mod:`options_platform.data.models`     — SQLAlchemy ORM models.
- :mod:`options_platform.data.repository` — repository pattern over models.
- :mod:`options_platform.data.market_data` — high-level market-data facade.
- :mod:`options_platform.data.providers`  — concrete data-source adapters.
"""

from options_platform.data.database import (
    Database,
    get_database,
    get_engine,
    get_session,
    session_scope,
    set_database,
)
from options_platform.data.market_data import MarketDataService
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
    VolatilityForecast,
)
from options_platform.data.repository import (
    BaseRepository,
    ForecastRepository,
    InstrumentRepository,
    PortfolioRepository,
    PositionRepository,
    TradeRepository,
)

__all__ = [
    "AssetClass",
    "Base",
    "BaseRepository",
    "Database",
    "ForecastModel",
    "ForecastRepository",
    "Instrument",
    "InstrumentRepository",
    "MarketDataService",
    "OptionType",
    "PortfolioRepository",
    "PortfolioSnapshot",
    "Position",
    "PositionRepository",
    "Trade",
    "TradeRepository",
    "TradeSide",
    "VolatilityForecast",
    "get_database",
    "get_engine",
    "get_session",
    "session_scope",
    "set_database",
]
