"""Fill-simulation primitives used by the paper broker."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from options_platform.trading.order import Order


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
    # TODO: market orders fill at the touch +/- slippage; limit orders only when
    # the touch crosses the limit; stop orders convert to market on trigger.
    raise NotImplementedError
