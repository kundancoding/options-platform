"""Runtime configuration for the Streamlit frontend.

Centralizes user-facing constants (page titles, default tickers, theme tweaks)
and exposes a single :func:`get_settings` accessor. Backend configuration lives
in :mod:`options_platform.utils` so the library remains usable without
Streamlit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_DB_PATH = DATA_DIR / "options_platform.db"


@dataclass(frozen=True)
class AppSettings:
    """Container for frontend-level settings."""

    app_title: str = "Options Platform"
    app_icon: str = ":chart_with_upwards_trend:"
    layout: str = "wide"
    default_ticker: str = "SPY"
    default_risk_free_rate: float = 0.045
    default_dividend_yield: float = 0.015
    db_path: Path = field(default=DEFAULT_DB_PATH)


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Return a cached :class:`AppSettings` instance."""
    return AppSettings()
