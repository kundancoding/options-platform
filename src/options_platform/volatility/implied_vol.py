"""Implied volatility solver.

Inverts the Black-Scholes price function for sigma using Brent's method with
a sensible bracket. Falls back to Newton-Raphson seeded with the Brenner-
Subrahmanyam approximation when the bracket fails.
"""

from __future__ import annotations

from options_platform.pricing.base import OptionContract


def implied_volatility(
    market_price: float,
    contract: OptionContract,
    *,
    tol: float = 1e-6,
    max_iter: int = 100,
) -> float:
    """Return the implied volatility that reproduces ``market_price``.

    ``contract.volatility`` is ignored — only the rest of the contract spec is
    used as the BSM input.
    """
    # TODO: scipy.optimize.brentq across [1e-6, 5.0]; Newton fallback.
    raise NotImplementedError
