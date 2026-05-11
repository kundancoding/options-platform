"""Simulated broker that consumes :class:`Order` objects and updates a portfolio."""

from __future__ import annotations

from dataclasses import dataclass

from options_platform.trading.execution import simulate_fill
from options_platform.trading.order import Order
from options_platform.trading.portfolio import Portfolio


@dataclass
class PaperBroker:
    """Routes orders through a fill simulator and mutates the portfolio."""

    portfolio: Portfolio
    commission_per_contract: float = 0.65
    slippage_bps: float = 1.0

    def submit(self, order: Order, quote: object) -> Order:
        """Submit an order against the current ``quote`` snapshot.

        Returns the order with updated status / fill price.
        """
        # TODO:
        # 1) validate buying power vs. portfolio.cash
        # 2) call simulate_fill(order, quote, slippage_bps)
        # 3) on fill, update self.portfolio (cash + positions) and commission
        # 4) persist the order + fill via the data layer (caller-injected repo).
        raise NotImplementedError

    def cancel(self, order_id: str) -> None:
        """Cancel a pending order."""
        # TODO: find by id; set status to CANCELLED if still PENDING.
        raise NotImplementedError
