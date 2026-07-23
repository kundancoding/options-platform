"""Option strategy construction.

A :class:`Strategy` is an ordered collection of signed contracts (legs) plus
metadata. Builders for common structures (vertical, straddle, condor, etc.)
return ready-to-price :class:`Strategy` instances.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from options_platform.pricing.base import OptionContract, OptionType


@dataclass
class Leg:
    """A signed option leg within a strategy."""

    contract: OptionContract
    quantity: int  # positive = long, negative = short


@dataclass
class Strategy:
    """A named collection of option legs."""

    name: str
    legs: list[Leg] = field(default_factory=list)

    def payoff_at_expiry(self, spot: float) -> float:
        """Return the strategy P&L at expiry for terminal price ``spot``."""
        if spot < 0:
            raise ValueError("spot must be non-negative")
        return float(sum(leg.quantity * _intrinsic(spot, leg.contract) for leg in self.legs))


StrategyKind = Literal[
    "long_call",
    "long_put",
    "covered_call",
    "protective_put",
    "bull_call_spread",
    "bear_put_spread",
    "straddle",
    "strangle",
    "iron_condor",
    "butterfly",
]


def build_strategy(kind: StrategyKind, **kwargs: object) -> Strategy:
    """Construct a named strategy from keyword inputs."""
    def contract(option_type: OptionType, strike: float | None = None) -> OptionContract:
        chosen_strike = float(kwargs.get("strike", 100.0) if strike is None else strike)
        return OptionContract(
            spot=float(kwargs.get("spot", 100.0)), strike=chosen_strike,
            time_to_expiry=float(kwargs.get("time_to_expiry", 1.0)),
            rate=float(kwargs.get("rate", 0.05)), dividend_yield=float(kwargs.get("dividend_yield", 0.0)),
            volatility=float(kwargs.get("volatility", 0.2)), option_type=option_type,
        )
    strike = float(kwargs.get("strike", 100.0))
    width = float(kwargs.get("width", 10.0))
    if width <= 0:
        raise ValueError("width must be positive")
    if kind == "long_call": return Strategy("Long Call", [Leg(contract(OptionType.CALL), 1)])
    if kind == "long_put": return Strategy("Long Put", [Leg(contract(OptionType.PUT), 1)])
    if kind == "bull_call_spread": return Strategy("Bull Call Spread", [Leg(contract(OptionType.CALL, strike), 1), Leg(contract(OptionType.CALL, strike + width), -1)])
    if kind == "bear_put_spread": return Strategy("Bear Put Spread", [Leg(contract(OptionType.PUT, strike + width), 1), Leg(contract(OptionType.PUT, strike), -1)])
    if kind == "straddle": return Strategy("Long Straddle", [Leg(contract(OptionType.CALL), 1), Leg(contract(OptionType.PUT), 1)])
    if kind == "strangle": return Strategy("Long Strangle", [Leg(contract(OptionType.PUT, strike - width), 1), Leg(contract(OptionType.CALL, strike + width), 1)])
    if kind == "butterfly": return Strategy("Long Call Butterfly", [Leg(contract(OptionType.CALL, strike - width), 1), Leg(contract(OptionType.CALL, strike), -2), Leg(contract(OptionType.CALL, strike + width), 1)])
    if kind == "iron_condor": return Strategy("Iron Condor", [Leg(contract(OptionType.PUT, strike - 2 * width), 1), Leg(contract(OptionType.PUT, strike - width), -1), Leg(contract(OptionType.CALL, strike + width), -1), Leg(contract(OptionType.CALL, strike + 2 * width), 1)])
    if kind in {"covered_call", "protective_put"}:
        raise ValueError(f"{kind} includes underlying stock and cannot be represented by option legs only")
    raise ValueError(f"unknown strategy kind: {kind}")


def _intrinsic(spot: float, contract: OptionContract) -> float:
    return max(spot - contract.strike, 0.0) if contract.option_type is OptionType.CALL else max(contract.strike - spot, 0.0)
