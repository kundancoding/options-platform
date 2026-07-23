"""Historical (realized) volatility estimators.

This module provides rolling realized-volatility estimators that operate on
pandas time series of asset prices. All estimators return *annualized*
volatility (``sigma * sqrt(periods_per_year)``) so outputs are directly
comparable across resampling frequencies and across the implied-vol layer.

Three families are exposed:

* :func:`log_returns` — utility for log-return computation with missing-data
  handling.
* :func:`rolling_realized_vol` / :func:`close_to_close_vol` — classic
  Andersen-style rolling close-to-close standard deviation of log returns.
* :func:`parkinson_vol`, :func:`garman_klass_vol`, :func:`yang_zhang_vol` —
  range-based estimators that exploit OHLC bars for higher statistical
  efficiency than C2C at the same sample size.

All routines accept a ``periods_per_year`` knob (default 252 for daily equity
bars) and gracefully tolerate missing values: NaNs are dropped from the
return series before the rolling reduction, and windows with too few
observations are flagged as NaN in the output rather than silently returning
biased estimates.
"""

from __future__ import annotations

from typing import Final

import numpy as np
import pandas as pd

from options_platform.utils.logging import get_logger

logger = get_logger(__name__)

DEFAULT_WINDOW: Final[int] = 21
DEFAULT_PERIODS_PER_YEAR: Final[int] = 252
MIN_OBSERVATIONS: Final[int] = 2


def _validate_window(window: int, *, min_value: int = MIN_OBSERVATIONS) -> None:
    """Raise ``ValueError`` if ``window`` is too small for a meaningful estimator."""
    if not isinstance(window, int) or isinstance(window, bool):
        raise TypeError(f"window must be int, got {type(window).__name__}")
    if window < min_value:
        raise ValueError(f"window must be >= {min_value}, got {window}")


def _validate_periods(periods_per_year: int) -> None:
    """Raise ``ValueError`` for a non-positive ``periods_per_year``."""
    if not isinstance(periods_per_year, int) or isinstance(periods_per_year, bool):
        raise TypeError(
            f"periods_per_year must be int, got {type(periods_per_year).__name__}"
        )
    if periods_per_year <= 0:
        raise ValueError(
            f"periods_per_year must be positive, got {periods_per_year}"
        )


def _ensure_series(prices: pd.Series, *, name: str) -> pd.Series:
    """Coerce input into a float ``pd.Series`` and validate."""
    if not isinstance(prices, pd.Series):
        raise TypeError(f"{name} must be a pandas Series, got {type(prices).__name__}")
    if prices.empty:
        raise ValueError(f"{name} is empty")
    return prices.astype("float64")


def log_returns(prices: pd.Series, *, drop_na: bool = True) -> pd.Series:
    """Return the log-return series of ``prices``.

    Computes ``ln(P_t / P_{t-1})``. Non-positive prices yield NaN to avoid
    propagating ``-inf`` through the rolling window. Leading NaN (from the
    first observation) is always present; intra-series NaNs are optionally
    forward-skipped via ``drop_na``.

    Parameters
    ----------
    prices:
        Time-indexed series of asset prices. Must be non-empty.
    drop_na:
        If True (default), drop NaN entries from the returned series so
        downstream rolling estimators are not biased by gaps. If False,
        preserve the original index alignment.

    Returns
    -------
    pd.Series
        Log returns, named ``"log_return"``.
    """
    series = _ensure_series(prices, name="prices")
    safe = series.where(series > 0, np.nan)
    returns = np.log(safe / safe.shift(1))
    returns.name = "log_return"
    if drop_na:
        return returns.dropna()
    return returns


def rolling_realized_vol(
    prices: pd.Series,
    *,
    window: int = DEFAULT_WINDOW,
    periods_per_year: int = DEFAULT_PERIODS_PER_YEAR,
    min_periods: int | None = None,
    ddof: int = 1,
) -> pd.Series:
    """Annualized rolling realized volatility of log returns.

    Parameters
    ----------
    prices:
        Time-indexed series of close prices.
    window:
        Rolling window length in observations. Must be ``>= 2``.
    periods_per_year:
        Annualization factor (252 trading days, 365 calendar days, 52 weeks,
        12 months, etc.). The output is ``std(returns) * sqrt(periods_per_year)``.
    min_periods:
        Minimum number of observations in the window required for a value
        to be emitted. Defaults to ``window`` (no partial windows).
    ddof:
        Delta degrees of freedom for the standard deviation. ``1`` (default)
        for the sample estimator; ``0`` for the population estimator.

    Returns
    -------
    pd.Series
        Annualized vol indexed by the *trailing* edge of the window, named
        ``"realized_vol"``. Entries with fewer than ``min_periods``
        observations are NaN.
    """
    _validate_window(window)
    _validate_periods(periods_per_year)
    series = _ensure_series(prices, name="prices")
    effective_min = window if min_periods is None else min_periods

    returns = log_returns(series, drop_na=False)
    rolling_std = returns.rolling(window=window, min_periods=effective_min).std(ddof=ddof)
    annualized = rolling_std * np.sqrt(periods_per_year)
    annualized.name = "realized_vol"
    logger.debug(
        "historical_vol.rolling_realized_vol",
        window=window,
        periods_per_year=periods_per_year,
        n_obs=int(returns.notna().sum()),
    )
    return annualized


def close_to_close_vol(
    prices: pd.Series,
    window: int = DEFAULT_WINDOW,
    *,
    periods_per_year: int = DEFAULT_PERIODS_PER_YEAR,
) -> pd.Series:
    """Alias for :func:`rolling_realized_vol` with the classic name.

    Kept for backwards compatibility with the rest of the platform; new code
    should prefer :func:`rolling_realized_vol` for clarity.
    """
    return rolling_realized_vol(
        prices, window=window, periods_per_year=periods_per_year
    )


def annualize_vol(
    sigma: float, *, periods_per_year: int = DEFAULT_PERIODS_PER_YEAR
) -> float:
    """Annualize a per-period standard deviation.

    ``sigma`` is the standard deviation of returns measured at the native
    frequency (e.g. daily). Multiplies by ``sqrt(periods_per_year)``.
    """
    _validate_periods(periods_per_year)
    if not np.isfinite(sigma) or sigma < 0:
        raise ValueError(f"sigma must be finite and non-negative, got {sigma}")
    return float(sigma * np.sqrt(periods_per_year))


def parkinson_vol(
    high: pd.Series,
    low: pd.Series,
    window: int = DEFAULT_WINDOW,
    *,
    periods_per_year: int = DEFAULT_PERIODS_PER_YEAR,
) -> pd.Series:
    """Parkinson high-low range estimator of annualized volatility.

    Per-bar variance is::

        (1 / (4 * ln 2)) * (ln(H / L))^2

    Averaged over the window and annualized by ``sqrt(periods_per_year)``.
    Parkinson is ~5x more efficient than C2C under continuous-time GBM with
    no drift, but is biased downward if the underlying drift is large.
    """
    _validate_window(window)
    _validate_periods(periods_per_year)
    high_s = _ensure_series(high, name="high")
    low_s = _ensure_series(low, name="low")
    if not high_s.index.equals(low_s.index):
        raise ValueError("high and low must share the same index")

    hl_ratio = (high_s / low_s).where((high_s > 0) & (low_s > 0))
    log_hl_sq = np.log(hl_ratio) ** 2
    factor = 1.0 / (4.0 * np.log(2.0))
    rolling_var = log_hl_sq.rolling(window=window, min_periods=window).mean() * factor
    annualized = np.sqrt(rolling_var.clip(lower=0)) * np.sqrt(periods_per_year)
    annualized.name = "parkinson_vol"
    return annualized


def garman_klass_vol(
    ohlc: pd.DataFrame,
    window: int = DEFAULT_WINDOW,
    *,
    periods_per_year: int = DEFAULT_PERIODS_PER_YEAR,
) -> pd.Series:
    """Garman-Klass OHLC estimator.

    Per-bar variance is::

        0.5 * (ln(H/L))^2 - (2*ln 2 - 1) * (ln(C/O))^2

    Roughly 7.4x more efficient than C2C for zero-drift GBM but ignores
    overnight gaps.
    """
    _validate_window(window)
    _validate_periods(periods_per_year)
    required = {"open", "high", "low", "close"}
    missing = required - set(ohlc.columns)
    if missing:
        raise ValueError(f"ohlc missing required columns: {sorted(missing)}")

    o = ohlc["open"].astype("float64")
    h = ohlc["high"].astype("float64")
    low = ohlc["low"].astype("float64")
    c = ohlc["close"].astype("float64")
    valid = (o > 0) & (h > 0) & (low > 0) & (c > 0)

    log_hl_sq = (np.log(h / low) ** 2).where(valid)
    log_co_sq = (np.log(c / o) ** 2).where(valid)
    per_bar = 0.5 * log_hl_sq - (2.0 * np.log(2.0) - 1.0) * log_co_sq

    rolling_var = per_bar.rolling(window=window, min_periods=window).mean()
    annualized = np.sqrt(rolling_var.clip(lower=0)) * np.sqrt(periods_per_year)
    annualized.name = "garman_klass_vol"
    return annualized


def yang_zhang_vol(
    ohlc: pd.DataFrame,
    window: int = DEFAULT_WINDOW,
    *,
    periods_per_year: int = DEFAULT_PERIODS_PER_YEAR,
) -> pd.Series:
    """Yang-Zhang OHLC estimator combining overnight, open-close and Rogers-Satchell.

    Handles both drift and overnight gaps. Decomposes as::

        sigma_yz^2 = sigma_overnight^2 + k * sigma_open_close^2 + (1 - k) * sigma_rs^2

    where ``k = 0.34 / (1.34 + (N+1)/(N-1))`` and ``N`` is the window length.
    Rogers-Satchell is drift-independent.
    """
    _validate_window(window, min_value=2)
    _validate_periods(periods_per_year)
    required = {"open", "high", "low", "close"}
    missing = required - set(ohlc.columns)
    if missing:
        raise ValueError(f"ohlc missing required columns: {sorted(missing)}")

    o = ohlc["open"].astype("float64")
    h = ohlc["high"].astype("float64")
    low = ohlc["low"].astype("float64")
    c = ohlc["close"].astype("float64")
    valid = (o > 0) & (h > 0) & (low > 0) & (c > 0)

    prev_close = c.shift(1)
    log_overnight = np.log(o / prev_close).where(valid & (prev_close > 0))
    log_open_close = np.log(c / o).where(valid)

    # Rogers-Satchell per-bar variance.
    log_ho = np.log(h / o)
    log_hc = np.log(h / c)
    log_lo = np.log(low / o)
    log_lc = np.log(low / c)
    rs = (log_ho * log_hc + log_lo * log_lc).where(valid)

    var_overnight = log_overnight.rolling(window=window, min_periods=window).var(ddof=1)
    var_open_close = log_open_close.rolling(window=window, min_periods=window).var(ddof=1)
    var_rs = rs.rolling(window=window, min_periods=window).mean()

    k = 0.34 / (1.34 + (window + 1) / (window - 1))
    var_yz = var_overnight + k * var_open_close + (1.0 - k) * var_rs
    annualized = np.sqrt(var_yz.clip(lower=0)) * np.sqrt(periods_per_year)
    annualized.name = "yang_zhang_vol"
    return annualized


__all__ = [
    "DEFAULT_PERIODS_PER_YEAR",
    "DEFAULT_WINDOW",
    "annualize_vol",
    "close_to_close_vol",
    "garman_klass_vol",
    "log_returns",
    "parkinson_vol",
    "rolling_realized_vol",
    "yang_zhang_vol",
]
