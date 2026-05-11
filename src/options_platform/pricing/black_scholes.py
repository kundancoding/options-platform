"""Black-Scholes-Merton closed-form pricer and analytic Greeks for European options.

Reference formulae (with continuous dividend yield ``q``)::

    d1 = (ln(S/K) + (r - q + 0.5 * sigma^2) * T) / (sigma * sqrt(T))
    d2 = d1 - sigma * sqrt(T)

    call = S * exp(-qT) * N(d1) - K * exp(-rT) * N(d2)
    put  = K * exp(-rT) * N(-d2) - S * exp(-qT) * N(-d1)

Greeks are returned in their *natural* units:

* ``delta``: per unit underlying.
* ``gamma``: per unit underlying squared.
* ``vega``: per unit volatility (``dV/dsigma``); divide by 100 for "per vol point".
* ``theta``: per year (negative for long options on average); divide by 365 for per-day.
* ``rho``: per unit rate; divide by 100 for "per basis point of rate (in %)".

Edge cases
----------
* ``T <= 0`` returns the intrinsic payoff and all sensitivities collapse to zero
  (delta becomes a step function at the strike — we return the right-limit at
  ``S == K`` to keep the function single-valued).
* ``sigma <= 0`` with ``T > 0`` is treated as a deterministic forward; the
  option is worth the discounted intrinsic of the forward price and all
  volatility-derived sensitivities (gamma, vega) are zero.
* Negative or zero ``spot``/``strike`` raises :class:`ValueError`.
"""

from __future__ import annotations

import math

from scipy.stats import norm

from options_platform.pricing.base import OptionContract, OptionType
from options_platform.utils.logging import get_logger

logger = get_logger(__name__)

_SQRT_EPS = 1e-12


def _validate(contract: OptionContract) -> None:
    """Raise :class:`ValueError` for inputs that violate BSM preconditions."""
    if contract.spot <= 0:
        raise ValueError(f"spot must be positive, got {contract.spot}")
    if contract.strike <= 0:
        raise ValueError(f"strike must be positive, got {contract.strike}")
    if contract.time_to_expiry < 0:
        raise ValueError(
            f"time_to_expiry must be non-negative, got {contract.time_to_expiry}"
        )
    if contract.volatility < 0:
        raise ValueError(f"volatility must be non-negative, got {contract.volatility}")


def _d1_d2(
    spot: float,
    strike: float,
    time_to_expiry: float,
    rate: float,
    dividend_yield: float,
    volatility: float,
) -> tuple[float, float]:
    """Return the standard BSM ``(d1, d2)`` pair.

    Caller is responsible for ensuring ``volatility * sqrt(T) > 0``.
    """
    vol_sqrt_t = volatility * math.sqrt(time_to_expiry)
    d1 = (
        math.log(spot / strike)
        + (rate - dividend_yield + 0.5 * volatility * volatility) * time_to_expiry
    ) / vol_sqrt_t
    d2 = d1 - vol_sqrt_t
    return d1, d2


def _intrinsic(spot: float, strike: float, option_type: OptionType) -> float:
    """Undiscounted intrinsic payoff at expiry."""
    if option_type is OptionType.CALL:
        return max(spot - strike, 0.0)
    return max(strike - spot, 0.0)


def call_price(
    spot: float,
    strike: float,
    time_to_expiry: float,
    rate: float,
    dividend_yield: float,
    volatility: float,
) -> float:
    """Price of a European call.

    See :func:`black_scholes_price` for parameter semantics.
    """
    if time_to_expiry <= 0 or volatility * math.sqrt(max(time_to_expiry, 0.0)) <= _SQRT_EPS:
        forward = spot * math.exp(-dividend_yield * max(time_to_expiry, 0.0))
        discounted_strike = strike * math.exp(-rate * max(time_to_expiry, 0.0))
        return max(forward - discounted_strike, 0.0)
    d1, d2 = _d1_d2(spot, strike, time_to_expiry, rate, dividend_yield, volatility)
    return spot * math.exp(-dividend_yield * time_to_expiry) * norm.cdf(d1) - strike * math.exp(
        -rate * time_to_expiry
    ) * norm.cdf(d2)


def put_price(
    spot: float,
    strike: float,
    time_to_expiry: float,
    rate: float,
    dividend_yield: float,
    volatility: float,
) -> float:
    """Price of a European put.

    See :func:`black_scholes_price` for parameter semantics.
    """
    if time_to_expiry <= 0 or volatility * math.sqrt(max(time_to_expiry, 0.0)) <= _SQRT_EPS:
        forward = spot * math.exp(-dividend_yield * max(time_to_expiry, 0.0))
        discounted_strike = strike * math.exp(-rate * max(time_to_expiry, 0.0))
        return max(discounted_strike - forward, 0.0)
    d1, d2 = _d1_d2(spot, strike, time_to_expiry, rate, dividend_yield, volatility)
    return strike * math.exp(-rate * time_to_expiry) * norm.cdf(-d2) - spot * math.exp(
        -dividend_yield * time_to_expiry
    ) * norm.cdf(-d1)


def black_scholes_price(contract: OptionContract) -> float:
    """Return the BSM price of a European option.

    Parameters
    ----------
    contract:
        Immutable :class:`OptionContract`. The ``exercise_style`` field is
        ignored — this pricer is European-only. Callers that pass an American
        contract will receive the European value (no early-exercise premium).

    Returns
    -------
    float
        The fair value of the contract under BSM.

    Raises
    ------
    ValueError
        If ``spot``/``strike`` are non-positive, or ``time_to_expiry``/
        ``volatility`` are negative.
    """
    _validate(contract)
    if contract.option_type is OptionType.CALL:
        price = call_price(
            contract.spot,
            contract.strike,
            contract.time_to_expiry,
            contract.rate,
            contract.dividend_yield,
            contract.volatility,
        )
    else:
        price = put_price(
            contract.spot,
            contract.strike,
            contract.time_to_expiry,
            contract.rate,
            contract.dividend_yield,
            contract.volatility,
        )
    logger.debug(
        "black_scholes_price",
        spot=contract.spot,
        strike=contract.strike,
        time_to_expiry=contract.time_to_expiry,
        rate=contract.rate,
        dividend_yield=contract.dividend_yield,
        volatility=contract.volatility,
        option_type=contract.option_type.value,
        price=price,
    )
    return price


def delta(contract: OptionContract) -> float:
    """First derivative of price with respect to spot.

    Returns ``exp(-qT) * N(d1)`` for calls and ``-exp(-qT) * N(-d1)`` for puts.
    At ``T == 0`` the delta is the right-limit step (``1`` / ``-1`` / ``0`` for
    ITM / ITM-put / OTM, with ATM treated as ITM by the right-limit convention).
    """
    _validate(contract)
    T = contract.time_to_expiry
    if T <= 0 or contract.volatility * math.sqrt(max(T, 0.0)) <= _SQRT_EPS:
        intrinsic_sign = 1.0 if contract.option_type is OptionType.CALL else -1.0
        if contract.option_type is OptionType.CALL:
            in_the_money = contract.spot >= contract.strike
        else:
            in_the_money = contract.spot <= contract.strike
        return intrinsic_sign if in_the_money else 0.0
    d1, _ = _d1_d2(
        contract.spot,
        contract.strike,
        T,
        contract.rate,
        contract.dividend_yield,
        contract.volatility,
    )
    discount = math.exp(-contract.dividend_yield * T)
    if contract.option_type is OptionType.CALL:
        return discount * norm.cdf(d1)
    return -discount * norm.cdf(-d1)


def gamma(contract: OptionContract) -> float:
    """Second derivative of price with respect to spot.

    Identical for calls and puts: ``exp(-qT) * phi(d1) / (S * sigma * sqrt(T))``.
    Returns ``0`` when ``T <= 0`` or ``sigma`` is effectively zero.
    """
    _validate(contract)
    T = contract.time_to_expiry
    if T <= 0 or contract.volatility * math.sqrt(max(T, 0.0)) <= _SQRT_EPS:
        return 0.0
    d1, _ = _d1_d2(
        contract.spot,
        contract.strike,
        T,
        contract.rate,
        contract.dividend_yield,
        contract.volatility,
    )
    return (
        math.exp(-contract.dividend_yield * T)
        * norm.pdf(d1)
        / (contract.spot * contract.volatility * math.sqrt(T))
    )


def vega(contract: OptionContract) -> float:
    """First derivative of price with respect to volatility (per unit sigma).

    Identical for calls and puts: ``S * exp(-qT) * phi(d1) * sqrt(T)``.
    Returns ``0`` when ``T <= 0`` or ``sigma`` is effectively zero.
    """
    _validate(contract)
    T = contract.time_to_expiry
    if T <= 0 or contract.volatility * math.sqrt(max(T, 0.0)) <= _SQRT_EPS:
        return 0.0
    d1, _ = _d1_d2(
        contract.spot,
        contract.strike,
        T,
        contract.rate,
        contract.dividend_yield,
        contract.volatility,
    )
    return (
        contract.spot
        * math.exp(-contract.dividend_yield * T)
        * norm.pdf(d1)
        * math.sqrt(T)
    )


def theta(contract: OptionContract) -> float:
    """First derivative of price with respect to *calendar* time (per year).

    Equivalent to ``-dV/dT`` where ``T`` is time-to-expiry — this is the
    market convention where a long option that decays as the clock advances
    has negative theta. Divide by 365 for per-day decay. Returns ``0`` when
    ``T <= 0`` or ``sigma`` is effectively zero.
    """
    _validate(contract)
    T = contract.time_to_expiry
    if T <= 0 or contract.volatility * math.sqrt(max(T, 0.0)) <= _SQRT_EPS:
        return 0.0
    S = contract.spot
    K = contract.strike
    r = contract.rate
    q = contract.dividend_yield
    sigma = contract.volatility
    d1, d2 = _d1_d2(S, K, T, r, q, sigma)
    pv_div = math.exp(-q * T)
    pv_rate = math.exp(-r * T)
    common = -(S * pv_div * norm.pdf(d1) * sigma) / (2.0 * math.sqrt(T))
    if contract.option_type is OptionType.CALL:
        return common - r * K * pv_rate * norm.cdf(d2) + q * S * pv_div * norm.cdf(d1)
    return common + r * K * pv_rate * norm.cdf(-d2) - q * S * pv_div * norm.cdf(-d1)


def rho(contract: OptionContract) -> float:
    """First derivative of price with respect to the risk-free rate.

    Returns ``K * T * exp(-rT) * N(d2)`` for calls and
    ``-K * T * exp(-rT) * N(-d2)`` for puts.
    Returns ``0`` when ``T <= 0``.
    """
    _validate(contract)
    T = contract.time_to_expiry
    if T <= 0:
        return 0.0
    if contract.volatility * math.sqrt(T) <= _SQRT_EPS:
        # Deterministic forward — rho is the derivative of the discounted
        # intrinsic w.r.t. r.
        forward = contract.spot * math.exp(-contract.dividend_yield * T)
        discounted_strike = contract.strike * math.exp(-contract.rate * T)
        if contract.option_type is OptionType.CALL:
            return T * discounted_strike if forward > discounted_strike else 0.0
        return -T * discounted_strike if forward < discounted_strike else 0.0
    _, d2 = _d1_d2(
        contract.spot,
        contract.strike,
        T,
        contract.rate,
        contract.dividend_yield,
        contract.volatility,
    )
    pv_rate = math.exp(-contract.rate * T)
    if contract.option_type is OptionType.CALL:
        return contract.strike * T * pv_rate * norm.cdf(d2)
    return -contract.strike * T * pv_rate * norm.cdf(-d2)


__all__ = [
    "black_scholes_price",
    "call_price",
    "put_price",
    "delta",
    "gamma",
    "vega",
    "theta",
    "rho",
]
