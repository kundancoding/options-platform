"""Per-symbol position bookkeeping."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass
class Position:
    """A held position in a single symbol (underlying or option).

    ``quantity`` is signed: positive = long, negative = short.
    ``avg_cost`` is the volume-weighted average entry price.
    """

    symbol: str
    quantity: int = 0
    avg_cost: float = 0.0
    realized_pnl: float = 0.0

    def apply_fill(self, side: str, quantity: int, price: float) -> None:
        """Update the position from an executed fill."""
        if side not in ("buy", "sell"):
            raise ValueError("side must be 'buy' or 'sell'")
        if quantity <= 0 or price < 0:
            raise ValueError("quantity must be positive and price non-negative")
        signed_fill = quantity if side == "buy" else -quantity
        old_quantity = self.quantity
        new_quantity = old_quantity + signed_fill
        if old_quantity == 0 or old_quantity * signed_fill > 0:
            self.avg_cost = (abs(old_quantity) * self.avg_cost + quantity * price) / abs(new_quantity)
        elif abs(signed_fill) <= abs(old_quantity):
            closed = quantity
            self.realized_pnl += closed * (price - self.avg_cost) * (1 if old_quantity > 0 else -1)
            if new_quantity == 0:
                self.avg_cost = 0.0
        else:
            closed = abs(old_quantity)
            self.realized_pnl += closed * (price - self.avg_cost) * (1 if old_quantity > 0 else -1)
            self.avg_cost = price
        self.quantity = new_quantity

    def unrealized_pnl(self, mark: float) -> float:
        """Mark-to-market P&L given the current ``mark`` price."""
        if mark < 0:
            raise ValueError("mark must be non-negative")
        return (mark - self.avg_cost) * self.quantity
