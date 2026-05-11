"""Option strategy construction.

A :class:`Strategy` is an ordered collection of signed contracts (legs) plus
metadata. Builders for common structures (vertical, straddle, condor, etc.)
return ready-to-price :class:`Strategy` instances.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from options_platform.pricing.base import OptionContract


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
        # TODO: sum of leg.quantity * intrinsic(spot, leg.contract).
        raise NotImplementedError


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
    # TODO: dispatch table per kind; raise on unknown kind.
    raise NotImplementedError
