"""Monte Carlo pricer for European-style payoffs.

Designed to be extensible to path-dependent payoffs (Asian, barrier, lookback)
in later iterations.
"""

from __future__ import annotations

from options_platform.pricing.base import OptionContract


def monte_carlo_price(
    contract: OptionContract,
    paths: int = 100_000,
    seed: int | None = None,
    antithetic: bool = True,
) -> float:
    """Price a European option via geometric Brownian motion simulation."""
    # TODO: vectorized simulation with numpy; return discounted expected payoff.
    # TODO: support antithetic variates and control variates for variance reduction.
    raise NotImplementedError
