"""Tests for the binomial-tree pricer."""

from __future__ import annotations

import pytest

from options_platform.pricing import binomial_price, black_scholes_price
from options_platform.pricing.base import ExerciseStyle, OptionContract


def test_binomial_converges_to_bs(atm_european_call: OptionContract) -> None:
    assert binomial_price(atm_european_call, steps=1_000) == pytest.approx(black_scholes_price(atm_european_call), abs=1e-2)


def test_american_put_is_not_cheaper_than_european(atm_european_put: OptionContract) -> None:
    american = OptionContract(**{**atm_european_put.__dict__, "exercise_style": ExerciseStyle.AMERICAN})
    assert binomial_price(american) >= binomial_price(atm_european_put)
