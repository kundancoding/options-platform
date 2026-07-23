"""Cox-Ross-Rubinstein binomial tree pricer (European & American).

Backward-induction on a recombining tree. Suitable for American exercise and
for sanity-checking the closed-form European result.
"""

from __future__ import annotations

import math

from options_platform.pricing.base import ExerciseStyle, OptionContract, OptionType


def binomial_price(contract: OptionContract, steps: int = 200) -> float:
    """Price an option on a CRR binomial tree with ``steps`` time steps."""
    if steps < 1:
        raise ValueError("steps must be at least 1")
    if contract.spot <= 0 or contract.strike <= 0:
        raise ValueError("spot and strike must be positive")
    if contract.time_to_expiry < 0 or contract.volatility < 0:
        raise ValueError("time_to_expiry and volatility must be non-negative")
    if contract.time_to_expiry == 0:
        return _intrinsic(contract.spot, contract.strike, contract.option_type)
    if contract.volatility == 0:
        forward_pv = contract.spot * math.exp(-contract.dividend_yield * contract.time_to_expiry)
        strike_pv = contract.strike * math.exp(-contract.rate * contract.time_to_expiry)
        return _intrinsic(forward_pv, strike_pv, contract.option_type)

    dt = contract.time_to_expiry / steps
    up = math.exp(contract.volatility * math.sqrt(dt))
    down = 1.0 / up
    growth = math.exp((contract.rate - contract.dividend_yield) * dt)
    probability = (growth - down) / (up - down)
    if not 0.0 <= probability <= 1.0:
        raise ValueError("invalid CRR risk-neutral probability; increase steps or check inputs")
    discount = math.exp(-contract.rate * dt)
    values = [
        _intrinsic(contract.spot * up ** (steps - j) * down**j, contract.strike, contract.option_type)
        for j in range(steps + 1)
    ]
    for level in range(steps - 1, -1, -1):
        next_values: list[float] = []
        for j in range(level + 1):
            continuation = discount * (probability * values[j] + (1.0 - probability) * values[j + 1])
            if contract.exercise_style is ExerciseStyle.AMERICAN:
                spot = contract.spot * up ** (level - j) * down**j
                continuation = max(continuation, _intrinsic(spot, contract.strike, contract.option_type))
            next_values.append(continuation)
        values = next_values
    return float(values[0])


def _intrinsic(spot: float, strike: float, option_type: OptionType) -> float:
    return max(spot - strike, 0.0) if option_type is OptionType.CALL else max(strike - spot, 0.0)
