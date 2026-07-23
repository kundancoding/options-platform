"""GARCH(1,1) volatility modeling via the ``arch`` package.

GARCH(1,1) parameterizes the conditional variance as::

    sigma_t^2 = omega + alpha * eps_{t-1}^2 + beta * sigma_{t-1}^2

with ``alpha, beta >= 0`` and ``alpha + beta < 1`` for covariance stationarity.
Unlike EWMA (which is the limiting case ``omega = 0``, ``alpha + beta = 1``),
GARCH(1,1) is mean-reverting: forecasts decay toward the unconditional
variance ``omega / (1 - alpha - beta)`` at speed ``alpha + beta``.

This module wraps :class:`arch.univariate.ARCHModel` to fit the model on a
price series, return per-period conditional volatility, and produce
multi-step variance forecasts. Returns are internally scaled by 100 to keep
the optimizer well-conditioned (a common idiom — typical equity log returns
are ~1e-2, which can cause the Hessian to become ill-conditioned); the
output is rescaled back to the original return units before annualization.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import numpy as np
import pandas as pd
from arch import arch_model
from arch.univariate.base import ARCHModelResult

from options_platform.utils.logging import get_logger
from options_platform.volatility.historical_vol import (
    DEFAULT_PERIODS_PER_YEAR,
    log_returns,
)

logger = get_logger(__name__)

DEFAULT_P: Final[int] = 1
DEFAULT_Q: Final[int] = 1
DEFAULT_RETURN_SCALE: Final[float] = 100.0
DEFAULT_FORECAST_HORIZON: Final[int] = 5
DEFAULT_MAX_ITER: Final[int] = 200


@dataclass(frozen=True)
class GarchFit:
    """Container for a fitted GARCH(1,1) model.

    Attributes
    ----------
    params:
        Estimated parameters keyed by name (``"omega"``, ``"alpha[1]"``,
        ``"beta[1]"``, plus the mean term, e.g. ``"mu"``).
    conditional_volatility:
        Annualized in-sample conditional volatility, indexed like the
        return series. Already rescaled back to the original return units.
    log_likelihood:
        Log-likelihood at convergence.
    aic:
        Akaike information criterion.
    bic:
        Bayesian information criterion.
    converged:
        True if the optimizer reported a successful exit; False otherwise.
        Even non-converged fits return usable point estimates, but callers
        should treat the standard errors with caution.
    periods_per_year:
        Annualization factor used to scale ``conditional_volatility``.
    return_scale:
        Multiplicative scale that was applied to returns prior to fitting.
        Forecasts produced via :func:`garch_forecast` use the same scale.
    unconditional_volatility:
        Per-period unconditional sigma = ``sqrt(omega / (1 - alpha - beta))``
        in *original* return units, annualized. ``None`` if the persistence
        ``alpha + beta >= 1`` (non-stationary fit).
    """

    params: dict[str, float]
    conditional_volatility: pd.Series
    log_likelihood: float
    aic: float
    bic: float
    converged: bool
    periods_per_year: int
    return_scale: float
    unconditional_volatility: float | None
    _result: ARCHModelResult


def _validate_horizon(horizon: int) -> None:
    if not isinstance(horizon, int) or isinstance(horizon, bool):
        raise TypeError(f"horizon must be int, got {type(horizon).__name__}")
    if horizon < 1:
        raise ValueError(f"horizon must be >= 1, got {horizon}")


def _validate_pq(p: int, q: int) -> None:
    for name, value in (("p", p), ("q", q)):
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(f"{name} must be int, got {type(value).__name__}")
        if value < 0:
            raise ValueError(f"{name} must be >= 0, got {value}")
    if p == 0 and q == 0:
        raise ValueError("at least one of p, q must be positive")


def _validate_periods(periods_per_year: int) -> None:
    if not isinstance(periods_per_year, int) or isinstance(periods_per_year, bool):
        raise TypeError(
            f"periods_per_year must be int, got {type(periods_per_year).__name__}"
        )
    if periods_per_year <= 0:
        raise ValueError(f"periods_per_year must be positive, got {periods_per_year}")


def _prepare_returns(
    prices_or_returns: pd.Series, *, is_returns: bool
) -> pd.Series:
    """Coerce input into a clean float return series."""
    if not isinstance(prices_or_returns, pd.Series):
        raise TypeError(
            f"input must be a pandas Series, got {type(prices_or_returns).__name__}"
        )
    if prices_or_returns.empty:
        raise ValueError("input series is empty")
    if is_returns:
        returns = prices_or_returns.astype("float64").dropna()
    else:
        returns = log_returns(prices_or_returns, drop_na=True)
    if len(returns) < 50:
        # GARCH(1,1) is technically identified with far fewer points, but
        # asymptotic standard errors require a reasonable sample.
        logger.warning(
            "garch.small_sample",
            n_obs=int(len(returns)),
            recommended_min=50,
        )
    return returns


def fit_garch(
    prices: pd.Series,
    *,
    p: int = DEFAULT_P,
    q: int = DEFAULT_Q,
    mean: str = "Constant",
    dist: str = "Normal",
    is_returns: bool = False,
    return_scale: float = DEFAULT_RETURN_SCALE,
    periods_per_year: int = DEFAULT_PERIODS_PER_YEAR,
    max_iter: int = DEFAULT_MAX_ITER,
) -> GarchFit:
    """Fit a GARCH(p, q) model (default GARCH(1,1)) to ``prices``.

    Parameters
    ----------
    prices:
        Time-indexed series. By default interpreted as prices and converted
        to log returns; set ``is_returns=True`` to pass returns directly.
    p, q:
        ARCH (``p``) and GARCH (``q``) lag orders. Default ``p = q = 1``.
    mean:
        Mean model. Forwarded to :func:`arch.arch_model`; common choices
        are ``"Constant"`` (default), ``"Zero"``, ``"AR"``, ``"HAR"``.
    dist:
        Innovation distribution. Forwarded to :func:`arch.arch_model`;
        e.g. ``"Normal"`` (default), ``"t"``, ``"skewt"``, ``"ged"``.
    is_returns:
        Set to True to pass returns directly instead of prices.
    return_scale:
        Multiplicative scale applied to returns before fitting (default
        100, so a 1% daily return becomes ``1.0`` and the optimizer sees
        well-conditioned magnitudes). All outputs are rescaled back.
    periods_per_year:
        Annualization factor for the output volatility series.
    max_iter:
        Maximum optimizer iterations. Forwarded as ``options={"maxiter": ...}``.

    Returns
    -------
    GarchFit
        Dataclass with the fitted parameters, annualized conditional vol
        series, fit diagnostics, and the underlying ``arch`` result object.

    Raises
    ------
    RuntimeError
        If the optimizer fails to produce a result (distinct from the
        non-convergence flag, which is reported on the returned object).
    """
    _validate_pq(p, q)
    _validate_periods(periods_per_year)
    if not np.isfinite(return_scale) or return_scale <= 0:
        raise ValueError(
            f"return_scale must be positive and finite, got {return_scale}"
        )
    if not isinstance(max_iter, int) or isinstance(max_iter, bool) or max_iter <= 0:
        raise ValueError(f"max_iter must be a positive int, got {max_iter}")

    returns = _prepare_returns(prices, is_returns=is_returns)
    scaled = returns * return_scale

    model = arch_model(
        scaled,
        mean=mean,
        vol="Garch",
        p=p,
        q=q,
        dist=dist,
        rescale=False,
    )
    try:
        result: ARCHModelResult = model.fit(
            disp="off",
            show_warning=False,
            options={"maxiter": max_iter},
        )
    except Exception as exc:  # arch raises a variety of errors; normalize.
        logger.error("garch.fit_failed", error=str(exc))
        raise RuntimeError(f"GARCH fit failed: {exc}") from exc

    converged = bool(result.convergence_flag == 0)
    if not converged:
        logger.warning(
            "garch.fit_did_not_converge",
            flag=int(result.convergence_flag),
        )

    # arch returns sigma in scaled units; divide by return_scale to recover
    # original units, then annualize.
    sigma_scaled = pd.Series(
        np.asarray(result.conditional_volatility, dtype="float64"),
        index=returns.index,
        name="garch_vol",
    )
    sigma_native = sigma_scaled / return_scale
    annualized = sigma_native * np.sqrt(periods_per_year)
    annualized.name = "garch_vol"

    params: dict[str, float] = {
        name: float(value) for name, value in result.params.items()
    }

    alpha = sum(
        value for name, value in params.items() if name.startswith("alpha")
    )
    beta = sum(
        value for name, value in params.items() if name.startswith("beta")
    )
    persistence = alpha + beta
    omega = params.get("omega")
    unconditional: float | None = None
    if omega is not None and persistence < 1.0 - 1e-8 and omega > 0:
        uncond_var_scaled = omega / (1.0 - persistence)
        uncond_sigma_native = np.sqrt(uncond_var_scaled) / return_scale
        unconditional = float(uncond_sigma_native * np.sqrt(periods_per_year))

    logger.info(
        "garch.fit_complete",
        converged=converged,
        log_likelihood=float(result.loglikelihood),
        persistence=float(persistence),
        n_obs=int(len(returns)),
    )

    return GarchFit(
        params=params,
        conditional_volatility=annualized,
        log_likelihood=float(result.loglikelihood),
        aic=float(result.aic),
        bic=float(result.bic),
        converged=converged,
        periods_per_year=periods_per_year,
        return_scale=return_scale,
        unconditional_volatility=unconditional,
        _result=result,
    )


def garch_forecast(
    fit: GarchFit,
    *,
    horizon: int = DEFAULT_FORECAST_HORIZON,
) -> pd.DataFrame:
    """Multi-step variance/volatility forecast from a fitted GARCH model.

    Uses the analytic GARCH(p, q) recursion baked into ``arch``'s
    :meth:`ARCHModelResult.forecast`. Forecasts originate from the *last*
    observation of the fit and mean-revert toward the unconditional
    variance at rate ``alpha + beta`` per step.

    Parameters
    ----------
    fit:
        The :class:`GarchFit` returned by :func:`fit_garch`.
    horizon:
        Number of steps ahead. Must be ``>= 1``.

    Returns
    -------
    pd.DataFrame
        Single-row DataFrame indexed by the forecast origin timestamp.
        Columns:

        * ``h=1`` … ``h={horizon}``: annualized vol forecast for that step.
        * ``cumulative_vol``: annualized vol over the full horizon, i.e.
          ``sqrt(sum_{h=1..H} sigma_h^2 * periods_per_year) /
          sqrt(periods_per_year)`` annualized — concretely the term-vol of
          a contract spanning ``horizon`` periods.
    """
    if not isinstance(fit, GarchFit):
        raise TypeError(f"fit must be a GarchFit, got {type(fit).__name__}")
    _validate_horizon(horizon)

    forecast = fit._result.forecast(horizon=horizon, reindex=False)
    variance_scaled = forecast.variance.iloc[-1].to_numpy(dtype="float64")
    # Convert from scaled-return variance to native-return variance.
    variance_native = variance_scaled / (fit.return_scale**2)
    sigma_native = np.sqrt(np.clip(variance_native, a_min=0.0, a_max=None))

    annual_factor = np.sqrt(fit.periods_per_year)
    per_step_annual = sigma_native * annual_factor
    # Cumulative variance over the horizon, annualized.
    cumulative_sigma_native = np.sqrt(variance_native.sum())
    cumulative_annual = cumulative_sigma_native * annual_factor

    columns = {f"h={h}": [per_step_annual[h - 1]] for h in range(1, horizon + 1)}
    columns["cumulative_vol"] = [cumulative_annual]
    origin_index = forecast.variance.index
    out = pd.DataFrame(columns, index=origin_index)
    out.index.name = "forecast_origin"
    return out


def garch_volatility(
    prices: pd.Series,
    *,
    p: int = DEFAULT_P,
    q: int = DEFAULT_Q,
    periods_per_year: int = DEFAULT_PERIODS_PER_YEAR,
    is_returns: bool = False,
) -> pd.Series:
    """Convenience: fit GARCH(p, q) and return only the in-sample vol series.

    Equivalent to ``fit_garch(prices, ...).conditional_volatility``. Useful
    when callers don't need the fit diagnostics or the forecast.
    """
    return fit_garch(
        prices,
        p=p,
        q=q,
        periods_per_year=periods_per_year,
        is_returns=is_returns,
    ).conditional_volatility


__all__ = [
    "DEFAULT_FORECAST_HORIZON",
    "DEFAULT_MAX_ITER",
    "DEFAULT_P",
    "DEFAULT_Q",
    "DEFAULT_RETURN_SCALE",
    "GarchFit",
    "fit_garch",
    "garch_forecast",
    "garch_volatility",
]
