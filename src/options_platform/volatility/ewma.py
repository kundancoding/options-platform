"""RiskMetrics-style exponentially weighted moving average (EWMA) volatility.

The EWMA variance recursion is::

    sigma_t^2 = lambda * sigma_{t-1}^2 + (1 - lambda) * r_t^2

with ``r_t = ln(P_t / P_{t-1})`` the log return. ``lambda`` controls memory:
the RiskMetrics 1996 daily default is ``0.94``; the monthly default is
``0.97``. Larger ``lambda`` means slower decay (longer effective memory).

The forecast in this model is *flat*: under a pure EWMA, the h-step-ahead
variance equals the current ``sigma_t^2`` for all ``h``. This module returns
the in-sample series and exposes :func:`ewma_forecast` for explicit horizon
forecasts so callers don't have to remember that property.

Annualization follows the historical-vol convention: per-period sigma is
scaled by ``sqrt(periods_per_year)``.
"""

from __future__ import annotations

from typing import Final

import numpy as np
import pandas as pd

from options_platform.utils.logging import get_logger
from options_platform.volatility.historical_vol import (
    DEFAULT_PERIODS_PER_YEAR,
    log_returns,
)

logger = get_logger(__name__)

RISKMETRICS_DAILY_LAMBDA: Final[float] = 0.94
RISKMETRICS_MONTHLY_LAMBDA: Final[float] = 0.97
DEFAULT_LAMBDA: Final[float] = RISKMETRICS_DAILY_LAMBDA


def _validate_lambda(lam: float) -> None:
    """``lambda`` must lie strictly inside ``(0, 1)``."""
    if not np.isfinite(lam):
        raise ValueError(f"lambda must be finite, got {lam}")
    if not 0.0 < lam < 1.0:
        raise ValueError(f"lambda must be in (0, 1), got {lam}")


def _validate_periods(periods_per_year: int) -> None:
    if not isinstance(periods_per_year, int) or isinstance(periods_per_year, bool):
        raise TypeError(
            f"periods_per_year must be int, got {type(periods_per_year).__name__}"
        )
    if periods_per_year <= 0:
        raise ValueError(f"periods_per_year must be positive, got {periods_per_year}")


def ewma_variance(
    returns: pd.Series,
    *,
    lam: float = DEFAULT_LAMBDA,
    initial_variance: float | None = None,
) -> pd.Series:
    """In-sample EWMA variance of a return series.

    Implements the recursion ``v_t = lam * v_{t-1} + (1 - lam) * r_t^2``.
    The initial state is seeded with ``initial_variance`` if supplied, else
    with the first non-NaN squared return (so the first emitted value equals
    that squared return).

    Parameters
    ----------
    returns:
        Per-period return series (typically log returns).
    lam:
        Decay parameter in ``(0, 1)``. Higher values give longer memory.
    initial_variance:
        Optional seed for ``v_0``. Must be non-negative. If ``None``, uses
        the first observation of ``r^2``.

    Returns
    -------
    pd.Series
        Per-period variance estimates aligned to the input index, named
        ``"ewma_variance"``. Entries before the first valid return are NaN.
    """
    if not isinstance(returns, pd.Series):
        raise TypeError(f"returns must be a pandas Series, got {type(returns).__name__}")
    _validate_lambda(lam)
    if initial_variance is not None:
        if not np.isfinite(initial_variance) or initial_variance < 0:
            raise ValueError(
                f"initial_variance must be finite and non-negative, got {initial_variance}"
            )

    r = returns.astype("float64")
    sq = r**2
    out = pd.Series(np.nan, index=r.index, name="ewma_variance", dtype="float64")

    prev: float | None = initial_variance
    for idx, value in sq.items():
        if not np.isfinite(value):
            # Propagate the prior state without updating; this gracefully
            # bridges over an isolated NaN.
            if prev is not None:
                out.loc[idx] = prev
            continue
        if prev is None:
            prev = float(value)
        else:
            prev = lam * prev + (1.0 - lam) * float(value)
        out.loc[idx] = prev
    return out


def ewma_volatility(
    prices: pd.Series,
    *,
    lam: float = DEFAULT_LAMBDA,
    periods_per_year: int = DEFAULT_PERIODS_PER_YEAR,
    initial_variance: float | None = None,
    annualize: bool = True,
) -> pd.Series:
    """Annualized EWMA volatility computed from a price series.

    Convenience wrapper that converts ``prices`` -> log returns -> EWMA
    variance -> sqrt -> annualization in one call.

    Parameters
    ----------
    prices:
        Time-indexed series of close prices.
    lam:
        EWMA decay parameter (default ``0.94`` per RiskMetrics 1996).
    periods_per_year:
        Annualization factor used when ``annualize`` is True.
    initial_variance:
        Optional seed for the variance recursion (in per-period units).
    annualize:
        If True (default), output is ``sigma * sqrt(periods_per_year)``.
        If False, the per-period sigma is returned.

    Returns
    -------
    pd.Series
        EWMA volatility series, named ``"ewma_vol"``.
    """
    _validate_lambda(lam)
    _validate_periods(periods_per_year)
    if not isinstance(prices, pd.Series):
        raise TypeError(f"prices must be a pandas Series, got {type(prices).__name__}")
    if prices.empty:
        raise ValueError("prices is empty")

    returns = log_returns(prices, drop_na=False)
    variance = ewma_variance(returns, lam=lam, initial_variance=initial_variance)
    sigma = np.sqrt(variance.clip(lower=0))
    if annualize:
        sigma = sigma * np.sqrt(periods_per_year)
    sigma.name = "ewma_vol"
    logger.debug(
        "ewma.volatility",
        lam=lam,
        periods_per_year=periods_per_year,
        annualize=annualize,
        n_obs=int(returns.notna().sum()),
    )
    return sigma


def ewma_forecast(
    prices: pd.Series,
    *,
    horizon: int = 1,
    lam: float = DEFAULT_LAMBDA,
    periods_per_year: int = DEFAULT_PERIODS_PER_YEAR,
    initial_variance: float | None = None,
) -> pd.DataFrame:
    """Multi-step-ahead EWMA volatility forecast.

    Under the pure EWMA recursion the conditional variance forecast is flat::

        E[sigma_{t+h}^2 | F_t] = sigma_t^2  for all h >= 1

    so the returned forecasts are identical across the horizon columns. This
    is intentional and matches RiskMetrics' specification; it also makes
    EWMA a convenient null baseline against GARCH, which adds mean-reversion.

    Parameters
    ----------
    prices:
        Time-indexed series of close prices.
    horizon:
        Number of steps ahead to emit. Must be ``>= 1``.
    lam:
        EWMA decay parameter.
    periods_per_year:
        Annualization factor; cumulative h-step variance is scaled to a
        per-year sigma via ``sqrt(periods_per_year)``.
    initial_variance:
        Optional seed for the variance recursion.

    Returns
    -------
    pd.DataFrame
        Indexed by the forecast *origin* (each row of the input series).
        Columns:

        * ``h=1`` … ``h={horizon}``: annualized vol forecast for that step.
        * ``cumulative_vol``: annualized vol over the full ``horizon`` steps,
          ``sqrt(h * sigma_t^2 * periods_per_year / periods_per_year)``
          which simplifies to ``sigma_t * sqrt(h) * sqrt(periods_per_year)``.
    """
    if not isinstance(horizon, int) or isinstance(horizon, bool):
        raise TypeError(f"horizon must be int, got {type(horizon).__name__}")
    if horizon < 1:
        raise ValueError(f"horizon must be >= 1, got {horizon}")
    _validate_lambda(lam)
    _validate_periods(periods_per_year)

    sigma_per_period = ewma_volatility(
        prices,
        lam=lam,
        periods_per_year=periods_per_year,
        initial_variance=initial_variance,
        annualize=False,
    )

    annual_factor = np.sqrt(periods_per_year)
    columns: dict[str, pd.Series] = {}
    for h in range(1, horizon + 1):
        # Flat per-step forecast under EWMA; annualize.
        columns[f"h={h}"] = sigma_per_period * annual_factor
    cumulative = sigma_per_period * np.sqrt(horizon) * annual_factor
    columns["cumulative_vol"] = cumulative

    forecast = pd.DataFrame(columns, index=sigma_per_period.index)
    forecast.index.name = sigma_per_period.index.name
    return forecast


__all__ = [
    "DEFAULT_LAMBDA",
    "RISKMETRICS_DAILY_LAMBDA",
    "RISKMETRICS_MONTHLY_LAMBDA",
    "ewma_forecast",
    "ewma_variance",
    "ewma_volatility",
]
