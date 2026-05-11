"""Tests for the binomial-tree pricer."""

from __future__ import annotations

import pytest

from options_platform.pricing import binomial_price
from options_platform.pricing.base import OptionContract


@pytest.mark.skip(reason="pricer not yet implemented")
def test_binomial_converges_to_bs(atm_european_call: OptionContract) -> None:
    # TODO: assert |binomial_price(c, steps=1000) - black_scholes_price(c)| < 1e-2
    raise NotImplementedError
