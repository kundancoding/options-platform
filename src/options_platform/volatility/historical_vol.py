"""Historical (realized) volatility estimators."""

from __future__ import annotations

import pandas as pd


def close_to_close_vol(prices: pd.Series, window: int = 21) -> pd.Series:
    """Annualized rolling close-to-close realized volatility."""
    # TODO: log returns -> rolling std -> sqrt(252) annualization.
    raise NotImplementedError


def parkinson_vol(high: pd.Series, low: pd.Series, window: int = 21) -> pd.Series:
    """Parkinson high-low estimator (more efficient than C2C)."""
    # TODO: (1/(4 ln 2)) * mean(ln(H/L)^2) over the window.
    raise NotImplementedError


def yang_zhang_vol(ohlc: pd.DataFrame, window: int = 21) -> pd.Series:
    """Yang-Zhang estimator combining overnight, open-close and Rogers-Satchell."""
    # TODO: implement the three components and the optimal weighting.
    raise NotImplementedError
