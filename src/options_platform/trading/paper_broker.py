"""Simulated broker that consumes :class:`Order` objects and updates a portfolio."""

from __future__ import annotations

from dataclasses import dataclass, field

from options_platform.trading.execution import simulate_fill
from options_platform.trading.order import Order, OrderSide, OrderStatus
from options_platform.trading.portfolio import Portfolio


@dataclass
class PaperBroker:
    """Routes orders through a fill simulator and mutates the portfolio."""

    portfolio: Portfolio
    commission_per_contract: float = 0.65
    slippage_bps: float = 1.0
    orders: dict[str, Order] = field(default_factory=dict)

    def submit(self, order: Order, quote: object) -> Order:
        """Submit an order against the current ``quote`` snapshot.

        Returns the order with updated status / fill price.
        """
        self.orders[order.order_id] = order
        if order.quantity <= 0:
            order.status = OrderStatus.REJECTED
            return order
        fill = simulate_fill(order, quote, slippage_bps=self.slippage_bps)
        if fill is None:
            return order
        gross = fill.quantity * fill.price
        fees = fill.quantity * self.commission_per_contract
        if order.side is OrderSide.BUY and self.portfolio.cash + 1e-12 < gross + fees:
            order.status = OrderStatus.REJECTED
            return order
        position = self.portfolio.get_or_create(order.symbol)
        position.apply_fill(order.side.value, fill.quantity, fill.price)
        self.portfolio.cash += -gross - fees if order.side is OrderSide.BUY else gross - fees
        order.filled_quantity = fill.quantity
        order.avg_fill_price = fill.price
        order.status = OrderStatus.FILLED
        return order

    def cancel(self, order_id: str) -> None:
        """Cancel a pending order."""
        order = self.orders.get(order_id)
        if order is None:
            raise KeyError(f"unknown order: {order_id}")
        if order.status is OrderStatus.PENDING:
            order.status = OrderStatus.CANCELLED
