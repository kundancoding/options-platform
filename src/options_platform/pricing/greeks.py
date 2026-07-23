"""Analytic Greeks for European options under Black-Scholes-Merton."""

from __future__ import annotations

from dataclasses import dataclass

from options_platform.pricing.base import OptionContract
from options_platform.pricing.black_scholes import delta, gamma, rho, theta, vega


@dataclass(frozen=True)
class Greeks:
    """First- and second-order sensitivities of an option price."""

    delta: float
    gamma: float
    vega: float
    theta: float
    rho: float


def compute_greeks(contract: OptionContract) -> Greeks:
    """Return analytic BSM Greeks for ``contract``.

    Vega is scaled per 1 vol point (i.e. dV/dsigma, not dV/d(sigma * 100)).
    Theta is per year; callers may convert to per-day in the UI.
    """
    return Greeks(
        delta=delta(contract),
        gamma=gamma(contract),
        vega=vega(contract),
        theta=theta(contract),
        rho=rho(contract),
    )
