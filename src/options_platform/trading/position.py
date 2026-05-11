"""Per-symbol position bookkeeping."""

from __future__ import annotations

from dataclasses import dataclass


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
        # TODO: weighted-average on adds; FIFO realized P&L on closes/reverses.
        raise NotImplementedError

    def unrealized_pnl(self, mark: float) -> float:
        """Mark-to-market P&L given the current ``mark`` price."""
        # TODO: (mark - avg_cost) * quantity * multiplier.
        raise NotImplementedError
