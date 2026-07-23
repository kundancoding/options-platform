"""Monte Carlo pricer for European-style payoffs.

Designed to be extensible to path-dependent payoffs (Asian, barrier, lookback)
in later iterations.
"""

from __future__ import annotations

import math

import numpy as np

from options_platform.pricing.base import OptionContract, OptionType


def monte_carlo_price(
    contract: OptionContract,
    paths: int = 100_000,
    seed: int | None = None,
    antithetic: bool = True,
) -> float:
    """Price a European option via geometric Brownian motion simulation."""
    if paths < 1:
        raise ValueError("paths must be positive")
    if contract.spot <= 0 or contract.strike <= 0:
        raise ValueError("spot and strike must be positive")
    if contract.time_to_expiry < 0 or contract.volatility < 0:
        raise ValueError("time_to_expiry and volatility must be non-negative")
    if contract.time_to_expiry == 0:
        return max(contract.spot - contract.strike, 0.0) if contract.option_type is OptionType.CALL else max(contract.strike - contract.spot, 0.0)

    rng = np.random.default_rng(seed)
    draws = rng.standard_normal((paths + 1) // 2 if antithetic else paths)
    if antithetic:
        draws = np.concatenate((draws, -draws))[:paths]
    t = contract.time_to_expiry
    terminal = contract.spot * np.exp(
        (contract.rate - contract.dividend_yield - 0.5 * contract.volatility**2) * t
        + contract.volatility * math.sqrt(t) * draws
    )
    payoff = np.maximum(terminal - contract.strike, 0.0) if contract.option_type is OptionType.CALL else np.maximum(contract.strike - terminal, 0.0)
    return float(math.exp(-contract.rate * t) * payoff.mean())
