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
        return self.positions.setdefault(symbol, Position(symbol=symbol))

    def equity(self, marks: dict[str, float]) -> float:
        """Cash plus mark-to-market value of all positions."""
        return self.cash + sum(position.quantity * float(marks.get(symbol, 0.0)) for symbol, position in self.positions.items())

    def aggregate_greeks(self, marks: dict[str, object]) -> dict[str, float]:
        """Return portfolio-level Greek aggregates (delta, gamma, vega, theta, rho)."""
        totals = {name: 0.0 for name in ("delta", "gamma", "vega", "theta", "rho")}
        for symbol, position in self.positions.items():
            greek = marks.get(symbol)
            if greek is None:
                continue
            for name in totals:
                totals[name] += position.quantity * float(getattr(greek, name, 0.0))
        return totals
