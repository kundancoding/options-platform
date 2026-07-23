"""Tests for the paper-broker flow."""

from __future__ import annotations

from options_platform.trading import Order, OrderSide, OrderStatus, OrderType, PaperBroker, Portfolio


def test_market_buy_decreases_cash_and_creates_position() -> None:
    portfolio = Portfolio(cash=10_000.0)
    result = PaperBroker(portfolio=portfolio, commission_per_contract=0.0, slippage_bps=0.0).submit(Order("SPY", OrderSide.BUY, 10, OrderType.MARKET), {"bid": 99.0, "ask": 100.0})
    assert result.status is OrderStatus.FILLED
    assert portfolio.positions["SPY"].quantity == 10
    assert portfolio.cash == 9_000.0
