"""Portfolio — collection of positions plus cash and aggregate metrics."""

from __future__ import annotations

from dataclasses import dataclass, field

from options_platform.trading.position import Position


@dataclass
class Portfolio:
    """A paper-trading account: cash + positions keyed by symbol."""

    cash: float = 100_000.0
    positions: dict[str, Position] = field(default_factory=dict)

    def get_or_create(self, symbol: str) -> Position:
        """Return the existing position or create an empty one."""
        # TODO: dict.setdefault on self.positions.
        raise NotImplementedError

    def equity(self, marks: dict[str, float]) -> float:
        """Cash plus mark-to-market value of all positions."""
        # TODO: sum cash + qty * mark across positions (handle option multiplier).
        raise NotImplementedError

    def aggregate_greeks(self, marks: dict[str, object]) -> dict[str, float]:
        """Return portfolio-level Greek aggregates (delta, gamma, vega, theta, rho)."""
        # TODO: sum per-leg Greeks weighted by signed quantity.
        raise NotImplementedError
