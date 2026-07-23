"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from options_platform.pricing.base import ExerciseStyle, OptionContract, OptionType


@pytest.fixture
def atm_european_call() -> OptionContract:
    """A vanilla at-the-money European call used across pricing tests."""
    return OptionContract(
        spot=100.0,
        strike=100.0,
        time_to_expiry=0.5,
        rate=0.045,
        dividend_yield=0.0,
        volatility=0.20,
        option_type=OptionType.CALL,
        exercise_style=ExerciseStyle.EUROPEAN,
    )


@pytest.fixture
def atm_european_put() -> OptionContract:
    """Mirror of :func:`atm_european_call` for the put side."""
    return OptionContract(
        spot=100.0,
        strike=100.0,
        time_to_expiry=0.5,
        rate=0.045,
        dividend_yield=0.0,
        volatility=0.20,
        option_type=OptionType.PUT,
        exercise_style=ExerciseStyle.EUROPEAN,
    )
