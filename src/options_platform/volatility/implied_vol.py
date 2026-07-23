"""Implied volatility solver.

Inverts the Black-Scholes price function for ``sigma`` given a market option
price. Uses :func:`scipy.optimize.brentq` to bracket and bisect the unique
zero of ``BSM(sigma) - market_price`` over a configurable sigma interval.

The Black-Scholes price is strictly monotone increasing in ``sigma`` (vega is
positive), so a sign change at the bracket endpoints guarantees a unique
root. The solver returns ``None`` when the problem is ill-posed (zero
time-to-expiry, invalid market price, no-arbitrage bound violated) or when
``brentq`` fails to converge inside the configured iteration budget.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Final

from scipy.optimize import brentq

from options_platform.pricing.base import OptionContract, OptionType
from options_platform.pricing.black_scholes import call_price, put_price
from options_platform.utils.logging import get_logger

logger = get_logger(__name__)

DEFAULT_SIGMA_LOW: Final[float] = 1e-6
DEFAULT_SIGMA_HIGH: Final[float] = 5.0
DEFAULT_TOL: Final[float] = 1e-8
DEFAULT_MAX_ITER: Final[int] = 100

_BOUND_EPS: Final[float] = 1e-12


def _no_arbitrage_bounds(
    contract: OptionContract,
) -> tuple[float, float]:
    """Return the lower/upper no-arbitrage bounds for ``contract``'s price.

    For a European call with continuous dividend yield ``q``::

        max(S * exp(-qT) - K * exp(-rT), 0)  <=  C  <=  S * exp(-qT)

    For a European put::

        max(K * exp(-rT) - S * exp(-qT), 0)  <=  P  <=  K * exp(-rT)
    """
    T = contract.time_to_expiry
    pv_spot = contract.spot * math.exp(-contract.dividend_yield * T)
    pv_strike = contract.strike * math.exp(-contract.rate * T)
    if contract.option_type is OptionType.CALL:
        return max(pv_spot - pv_strike, 0.0), pv_spot
    return max(pv_strike - pv_spot, 0.0), pv_strike


def _price_at(contract: OptionContract, sigma: float) -> float:
    """Black-Scholes price of ``contract`` at the given trial volatility."""
    if contract.option_type is OptionType.CALL:
        return call_price(
            contract.spot,
            contract.strike,
            contract.time_to_expiry,
            contract.rate,
            contract.dividend_yield,
            sigma,
        )
    return put_price(
        contract.spot,
        contract.strike,
        contract.time_to_expiry,
        contract.rate,
        contract.dividend_yield,
        sigma,
    )


def implied_volatility(
    market_price: float,
    contract: OptionContract,
    *,
    sigma_low: float = DEFAULT_SIGMA_LOW,
    sigma_high: float = DEFAULT_SIGMA_HIGH,
    tol: float = DEFAULT_TOL,
    max_iter: int = DEFAULT_MAX_ITER,
) -> float | None:
    """Return the implied volatility that reproduces ``market_price``.

    Inverts the Black-Scholes-Merton price function for ``sigma`` using
    Brent's method on the interval ``[sigma_low, sigma_high]``. The
    ``volatility`` field on ``contract`` is ignored — only the remaining
    contract spec (spot, strike, T, r, q, option type) is used as the BSM
    input.

    Parameters
    ----------
    market_price:
        Observed market price of the option. Must be finite and non-negative.
    contract:
        Option contract spec. ``contract.volatility`` is ignored.
    sigma_low, sigma_high:
        Inclusive endpoints of the sigma search interval. Must satisfy
        ``0 < sigma_low < sigma_high``. Defaults span 0.0001%-500% vol,
        which comfortably covers any real-world equity/FX market.
    tol:
        Absolute tolerance forwarded to :func:`scipy.optimize.brentq` (the
        ``xtol`` argument). The solver halts when the bracket width falls
        below this value.
    max_iter:
        Maximum number of Brent iterations. Forwarded as ``maxiter``.

    Returns
    -------
    float or None
        The implied volatility, or ``None`` if any of the following holds:

        * ``market_price`` is non-finite or negative;
        * ``contract.time_to_expiry <= 0`` (IV is undefined at expiry);
        * the price violates the no-arbitrage bounds for ``contract``;
        * ``brentq`` fails to converge within ``max_iter`` iterations.

    Raises
    ------
    ValueError
        If ``sigma_low``/``sigma_high`` form an invalid interval or
        ``max_iter`` is non-positive.
    """
    if not (math.isfinite(sigma_low) and math.isfinite(sigma_high)):
        raise ValueError(
            f"sigma_low and sigma_high must be finite, got [{sigma_low}, {sigma_high}]"
        )
    if sigma_low <= 0 or sigma_high <= sigma_low:
        raise ValueError(
            f"require 0 < sigma_low < sigma_high, got [{sigma_low}, {sigma_high}]"
        )
    if max_iter <= 0:
        raise ValueError(f"max_iter must be positive, got {max_iter}")

    if not math.isfinite(market_price) or market_price < 0:
        logger.warning(
            "implied_volatility.invalid_market_price",
            market_price=market_price,
        )
        return None

    if contract.time_to_expiry <= 0:
        logger.warning(
            "implied_volatility.zero_time_to_expiry",
            time_to_expiry=contract.time_to_expiry,
        )
        return None

    lower_bound, upper_bound = _no_arbitrage_bounds(contract)
    if (
        market_price < lower_bound - _BOUND_EPS
        or market_price > upper_bound + _BOUND_EPS
    ):
        logger.warning(
            "implied_volatility.no_arbitrage_violation",
            market_price=market_price,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            option_type=contract.option_type.value,
        )
        return None

    # contract.volatility is ignored — replace with a sentinel that BSM accepts.
    spec = replace(contract, volatility=sigma_low)

    def objective(sigma: float) -> float:
        return _price_at(spec, sigma) - market_price

    f_low = objective(sigma_low)
    f_high = objective(sigma_high)
    if f_low * f_high > 0:
        logger.warning(
            "implied_volatility.bracket_no_sign_change",
            market_price=market_price,
            sigma_low=sigma_low,
            sigma_high=sigma_high,
            f_low=f_low,
            f_high=f_high,
        )
        return None

    try:
        iv, result = brentq(
            objective,
            sigma_low,
            sigma_high,
            xtol=tol,
            maxiter=max_iter,
            full_output=True,
            disp=False,
        )
    except (RuntimeError, ValueError) as exc:
        logger.warning(
            "implied_volatility.brentq_failed",
            market_price=market_price,
            sigma_low=sigma_low,
            sigma_high=sigma_high,
            error=str(exc),
        )
        return None

    if not result.converged:
        logger.warning(
            "implied_volatility.brentq_not_converged",
            market_price=market_price,
            iterations=result.iterations,
            flag=result.flag,
        )
        return None

    logger.debug(
        "implied_volatility.converged",
        market_price=market_price,
        implied_vol=iv,
        option_type=contract.option_type.value,
        spot=contract.spot,
        strike=contract.strike,
        time_to_expiry=contract.time_to_expiry,
    )
    return float(iv)


__all__ = [
    "DEFAULT_MAX_ITER",
    "DEFAULT_SIGMA_HIGH",
    "DEFAULT_SIGMA_LOW",
    "DEFAULT_TOL",
    "implied_volatility",
]
