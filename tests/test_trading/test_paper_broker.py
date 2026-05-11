"""Tests for the paper-broker flow."""

from __future__ import annotations

import pytest

from options_platform.trading import PaperBroker, Portfolio


@pytest.mark.skip(reason="paper broker not yet implemented")
def test_market_buy_decreases_cash_and_creates_position() -> None:
    portfolio = Portfolio(cash=10_000.0)
    broker = PaperBroker(portfolio=portfolio)
    _ = broker
    # TODO: submit Order(BUY 10 SPY MARKET); assert cash and position update.
    raise NotImplementedError
