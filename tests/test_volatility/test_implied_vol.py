"""Tests for the implied-volatility solver."""

from __future__ import annotations

import pytest

from options_platform.volatility import implied_volatility


@pytest.mark.skip(reason="IV solver not yet implemented")
def test_iv_round_trips(atm_european_call) -> None:  # type: ignore[no-untyped-def]
    # TODO: price under known sigma, then assert solver recovers sigma to 1e-4.
    _ = implied_volatility
    raise NotImplementedError
