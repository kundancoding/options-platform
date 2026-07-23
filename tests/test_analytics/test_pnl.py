"""Tests for Greek P&L attribution."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from options_platform.analytics import attribute_pnl


def test_components_sum_to_total() -> None:
    greek = SimpleNamespace(delta=0.5, gamma=0.02, vega=10.0, theta=-2.0, rho=3.0)
    breakdown = attribute_pnl(prev_mark=10.0, curr_mark=11.57, greeks_prev=greek, delta_spot=2.0, delta_vol=0.1, delta_t=0.25, delta_rate=0.01)
    assert breakdown.total == pytest.approx(1.57)
    assert breakdown.residual == pytest.approx(0.0)
