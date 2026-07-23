"""Fill-simulation primitives used by the paper broker."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from options_platform.trading.order import Order, OrderSide, OrderType


class ExecutionVenue(str, Enum):
    """Where the simulated order is routed."""

    SIMULATED = "simulated"


@dataclass
class Fill:
    """A single executed fill against an order."""

    order_id: str
    quantity: int
    price: float


def simulate_fill(order: Order, quote: object, *, slippage_bps: float = 1.0) -> Fill | None:
    """Decide if ``order`` fills against ``quote`` and at what price.

    Returns ``None`` when the order remains resting (e.g. unmarketable limit).
    """
    if order.quantity <= 0 or slippage_bps < 0:
        raise ValueError("order quantity must be positive and slippage_bps non-negative")
    bid, ask, last = _quote_values(quote)
    buy = order.side is OrderSide.BUY
    touch = ask if buy else bid
    triggered = order.order_type not in (OrderType.STOP, OrderType.STOP_LIMIT)
    if not triggered:
        if order.stop_price is None:
            raise ValueError("stop orders require stop_price")
        trigger = ask if buy else bid
        triggered = trigger >= order.stop_price if buy else trigger <= order.stop_price
    if not triggered:
        return None
    if order.order_type in (OrderType.LIMIT, OrderType.STOP_LIMIT):
        if order.limit_price is None:
            raise ValueError("limit orders require limit_price")
        if (buy and touch > order.limit_price) or (not buy and touch < order.limit_price):
            return None
        price = min(touch, order.limit_price) if buy else max(touch, order.limit_price)
    else:
        price = touch
    adjustment = price * slippage_bps / 10_000.0
    return Fill(order.order_id, order.quantity, price + adjustment if buy else max(0.0, price - adjustment))


def _quote_values(quote: object) -> tuple[float, float, float]:
    def value(name: str) -> float | None:
        raw = quote.get(name) if isinstance(quote, dict) else getattr(quote, name, None)
        return None if raw is None else float(raw)
    bid, ask, last = value("bid"), value("ask"), value("last")
    if last is None and bid is None and ask is None:
        raise ValueError("quote must contain at least one of bid, ask, or last")
    mid = last if last is not None else (bid if bid is not None else ask)
    assert mid is not None
    return (bid if bid is not None else mid, ask if ask is not None else mid, mid)
