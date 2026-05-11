"""Tests for analytic Greeks."""

from __future__ import annotations

import pytest

from options_platform.pricing import compute_greeks
from options_platform.pricing.base import OptionContract


@pytest.mark.skip(reason="Greeks not yet implemented")
def test_call_delta_in_unit_interval(atm_european_call: OptionContract) -> None:
    g = compute_greeks(atm_european_call)
    assert 0.0 <= g.delta <= 1.0


@pytest.mark.skip(reason="Greeks not yet implemented")
def test_gamma_non_negative(atm_european_call: OptionContract) -> None:
    assert compute_greeks(atm_european_call).gamma >= 0.0
