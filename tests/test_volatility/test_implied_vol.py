"""Tests for the implied-volatility solver."""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from options_platform.pricing.base import ExerciseStyle, OptionContract, OptionType
from options_platform.pricing.black_scholes import black_scholes_price
from options_platform.volatility import implied_volatility


# --- Round-trip: recover known sigma ---------------------------------------


@pytest.mark.parametrize("sigma", [0.05, 0.10, 0.20, 0.35, 0.60, 1.00])
def test_iv_round_trip_call(atm_european_call: OptionContract, sigma: float) -> None:
    """Price an ATM call under ``sigma``, then recover ``sigma`` from price."""
    contract = replace(atm_european_call, volatility=sigma)
    price = black_scholes_price(contract)
    iv = implied_volatility(price, contract)
    assert iv is not None
    assert iv == pytest.approx(sigma, abs=1e-6)


@pytest.mark.parametrize("sigma", [0.05, 0.10, 0.20, 0.35, 0.60, 1.00])
def test_iv_round_trip_put(atm_european_put: OptionContract, sigma: float) -> None:
    """Same round-trip for a put."""
    contract = replace(atm_european_put, volatility=sigma)
    price = black_scholes_price(contract)
    iv = implied_volatility(price, contract)
    assert iv is not None
    assert iv == pytest.approx(sigma, abs=1e-6)


def test_iv_round_trip_otm_call() -> None:
    """OTM call — strike 120, spot 100 — recover sigma."""
    contract = OptionContract(
        spot=100.0,
        strike=120.0,
        time_to_expiry=1.0,
        rate=0.03,
        dividend_yield=0.01,
        volatility=0.25,
        option_type=OptionType.CALL,
        exercise_style=ExerciseStyle.EUROPEAN,
    )
    price = black_scholes_price(contract)
    iv = implied_volatility(price, contract)
    assert iv is not None
    assert iv == pytest.approx(0.25, abs=1e-6)


def test_iv_round_trip_itm_put() -> None:
    """Deep ITM put — sanity-check that the bracket still works."""
    contract = OptionContract(
        spot=80.0,
        strike=100.0,
        time_to_expiry=0.25,
        rate=0.05,
        dividend_yield=0.0,
        volatility=0.40,
        option_type=OptionType.PUT,
        exercise_style=ExerciseStyle.EUROPEAN,
    )
    price = black_scholes_price(contract)
    iv = implied_volatility(price, contract)
    assert iv is not None
    assert iv == pytest.approx(0.40, abs=1e-6)


def test_iv_ignores_contract_volatility_field(
    atm_european_call: OptionContract,
) -> None:
    """The solver must ignore ``contract.volatility`` — only the market price matters."""
    true_sigma = 0.30
    priced = replace(atm_european_call, volatility=true_sigma)
    price = black_scholes_price(priced)
    # Pass a contract with a different sigma; solver should still recover 0.30.
    misleading = replace(atm_european_call, volatility=0.05)
    iv = implied_volatility(price, misleading)
    assert iv is not None
    assert iv == pytest.approx(true_sigma, abs=1e-6)


# --- Invalid market prices --------------------------------------------------


def test_iv_negative_price_returns_none(atm_european_call: OptionContract) -> None:
    assert implied_volatility(-1.0, atm_european_call) is None


def test_iv_nan_price_returns_none(atm_european_call: OptionContract) -> None:
    assert implied_volatility(float("nan"), atm_european_call) is None


def test_iv_inf_price_returns_none(atm_european_call: OptionContract) -> None:
    assert implied_volatility(float("inf"), atm_european_call) is None


def test_iv_price_below_intrinsic_returns_none(
    atm_european_call: OptionContract,
) -> None:
    """A price below the lower no-arbitrage bound is unrecoverable."""
    deep_itm = replace(atm_european_call, spot=200.0, strike=100.0)
    # Lower bound for this call is S*exp(-qT) - K*exp(-rT) > 0; quote below it.
    assert implied_volatility(0.01, deep_itm) is None


def test_iv_price_above_upper_bound_returns_none(
    atm_european_call: OptionContract,
) -> None:
    """A call cannot exceed ``S * exp(-qT)``."""
    upper_violation = atm_european_call.spot * math.exp(
        -atm_european_call.dividend_yield * atm_european_call.time_to_expiry
    ) + 10.0
    assert implied_volatility(upper_violation, atm_european_call) is None


def test_iv_put_price_above_upper_bound_returns_none(
    atm_european_put: OptionContract,
) -> None:
    """A put cannot exceed ``K * exp(-rT)``."""
    upper_violation = atm_european_put.strike * math.exp(
        -atm_european_put.rate * atm_european_put.time_to_expiry
    ) + 10.0
    assert implied_volatility(upper_violation, atm_european_put) is None


# --- Boundary / degenerate cases -------------------------------------------


def test_iv_zero_time_to_expiry_returns_none(
    atm_european_call: OptionContract,
) -> None:
    """At expiry, IV is undefined — any non-intrinsic price is meaningless."""
    expired = replace(atm_european_call, time_to_expiry=0.0)
    assert implied_volatility(0.0, expired) is None


def test_iv_negative_time_to_expiry_returns_none(
    atm_european_call: OptionContract,
) -> None:
    bad = replace(atm_european_call, time_to_expiry=-0.1)
    assert implied_volatility(1.0, bad) is None


# --- Convergence-failure / bracket-config cases ----------------------------


def test_iv_narrow_bracket_excludes_true_sigma_returns_none(
    atm_european_call: OptionContract,
) -> None:
    """If the user-supplied bracket doesn't straddle the root, return None."""
    contract = replace(atm_european_call, volatility=0.30)
    price = black_scholes_price(contract)
    # True IV is 0.30 but we search inside [0.01, 0.05] — no sign change.
    iv = implied_volatility(price, contract, sigma_low=0.01, sigma_high=0.05)
    assert iv is None


def test_iv_invalid_bracket_raises(atm_european_call: OptionContract) -> None:
    with pytest.raises(ValueError):
        implied_volatility(5.0, atm_european_call, sigma_low=0.5, sigma_high=0.1)


def test_iv_nonpositive_sigma_low_raises(atm_european_call: OptionContract) -> None:
    with pytest.raises(ValueError):
        implied_volatility(5.0, atm_european_call, sigma_low=0.0, sigma_high=1.0)


def test_iv_nonpositive_max_iter_raises(atm_european_call: OptionContract) -> None:
    with pytest.raises(ValueError):
        implied_volatility(5.0, atm_european_call, max_iter=0)


def test_iv_max_iter_too_low_returns_none(
    atm_european_call: OptionContract,
) -> None:
    """An impossibly tight iteration budget should yield ``None``, not a crash."""
    contract = replace(atm_european_call, volatility=0.30)
    price = black_scholes_price(contract)
    iv = implied_volatility(price, contract, max_iter=1, tol=1e-15)
    # Brent typically converges quadratically and may still succeed in 1 iter
    # for some inputs; the contract is "no crash + None on failure".
    assert iv is None or iv == pytest.approx(0.30, abs=1e-2)


# --- Solver tolerance / consistency ----------------------------------------


def test_iv_recovered_price_matches_market(atm_european_call: OptionContract) -> None:
    """Re-pricing at the recovered IV must reproduce the market price."""
    contract = replace(atm_european_call, volatility=0.27)
    price = black_scholes_price(contract)
    iv = implied_volatility(price, contract)
    assert iv is not None
    recovered = black_scholes_price(replace(contract, volatility=iv))
    assert recovered == pytest.approx(price, abs=1e-8)


def test_iv_call_and_put_consistent_via_parity() -> None:
    """Call and put at the same strike/expiry should imply the same vol."""
    base = OptionContract(
        spot=100.0,
        strike=105.0,
        time_to_expiry=0.75,
        rate=0.04,
        dividend_yield=0.02,
        volatility=0.22,
        option_type=OptionType.CALL,
        exercise_style=ExerciseStyle.EUROPEAN,
    )
    put = replace(base, option_type=OptionType.PUT)
    iv_call = implied_volatility(black_scholes_price(base), base)
    iv_put = implied_volatility(black_scholes_price(put), put)
    assert iv_call is not None and iv_put is not None
    assert iv_call == pytest.approx(iv_put, abs=1e-6)
