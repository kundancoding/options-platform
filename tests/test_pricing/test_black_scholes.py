"""Tests for the Black-Scholes pricer and analytic Greeks."""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from options_platform.pricing import black_scholes_price
from options_platform.pricing.base import ExerciseStyle, OptionContract, OptionType
from options_platform.pricing.black_scholes import (
    call_price,
    delta,
    gamma,
    put_price,
    rho,
    theta,
    vega,
)


# --- Pricing ---------------------------------------------------------------


def test_atm_call_price_is_positive(atm_european_call: OptionContract) -> None:
    assert black_scholes_price(atm_european_call) > 0


def test_atm_put_price_is_positive(atm_european_put: OptionContract) -> None:
    assert black_scholes_price(atm_european_put) > 0


def test_put_call_parity(
    atm_european_call: OptionContract,
    atm_european_put: OptionContract,
) -> None:
    # c - p == S * exp(-qT) - K * exp(-rT)
    c = black_scholes_price(atm_european_call)
    p = black_scholes_price(atm_european_put)
    expected = atm_european_call.spot * math.exp(
        -atm_european_call.dividend_yield * atm_european_call.time_to_expiry
    ) - atm_european_call.strike * math.exp(
        -atm_european_call.rate * atm_european_call.time_to_expiry
    )
    assert c - p == pytest.approx(expected, abs=1e-10)


def test_known_value_hull_textbook() -> None:
    """Hull, Options Futures & Other Derivatives — worked example.

    S=42, K=40, r=0.1, q=0, sigma=0.2, T=0.5 → call ~ 4.759, put ~ 0.808.
    """
    contract = OptionContract(
        spot=42.0,
        strike=40.0,
        time_to_expiry=0.5,
        rate=0.10,
        dividend_yield=0.0,
        volatility=0.20,
        option_type=OptionType.CALL,
    )
    assert black_scholes_price(contract) == pytest.approx(4.759, abs=1e-3)
    put = replace(contract, option_type=OptionType.PUT)
    assert black_scholes_price(put) == pytest.approx(0.808, abs=1e-3)


def test_deep_itm_call_approaches_discounted_forward() -> None:
    contract = OptionContract(
        spot=200.0,
        strike=50.0,
        time_to_expiry=1.0,
        rate=0.05,
        dividend_yield=0.02,
        volatility=0.20,
        option_type=OptionType.CALL,
    )
    expected = contract.spot * math.exp(-contract.dividend_yield * contract.time_to_expiry) - (
        contract.strike * math.exp(-contract.rate * contract.time_to_expiry)
    )
    assert black_scholes_price(contract) == pytest.approx(expected, rel=1e-6)


def test_deep_otm_call_is_near_zero() -> None:
    contract = OptionContract(
        spot=50.0,
        strike=500.0,
        time_to_expiry=0.25,
        rate=0.04,
        dividend_yield=0.0,
        volatility=0.20,
        option_type=OptionType.CALL,
    )
    assert black_scholes_price(contract) == pytest.approx(0.0, abs=1e-8)


def test_zero_time_to_expiry_returns_intrinsic() -> None:
    itm_call = OptionContract(
        spot=110.0,
        strike=100.0,
        time_to_expiry=0.0,
        rate=0.05,
        dividend_yield=0.0,
        volatility=0.20,
        option_type=OptionType.CALL,
    )
    assert black_scholes_price(itm_call) == pytest.approx(10.0)

    otm_put = replace(itm_call, option_type=OptionType.PUT)
    assert black_scholes_price(otm_put) == pytest.approx(0.0)


def test_zero_volatility_returns_discounted_intrinsic() -> None:
    # With sigma = 0 the option is a forward — value is max(F - K*exp(-rT), 0).
    contract = OptionContract(
        spot=100.0,
        strike=95.0,
        time_to_expiry=1.0,
        rate=0.05,
        dividend_yield=0.01,
        volatility=0.0,
        option_type=OptionType.CALL,
    )
    forward = contract.spot * math.exp(-contract.dividend_yield * contract.time_to_expiry)
    pv_strike = contract.strike * math.exp(-contract.rate * contract.time_to_expiry)
    assert black_scholes_price(contract) == pytest.approx(max(forward - pv_strike, 0.0))


def test_call_price_helper_matches_dispatcher(atm_european_call: OptionContract) -> None:
    via_helper = call_price(
        atm_european_call.spot,
        atm_european_call.strike,
        atm_european_call.time_to_expiry,
        atm_european_call.rate,
        atm_european_call.dividend_yield,
        atm_european_call.volatility,
    )
    assert via_helper == pytest.approx(black_scholes_price(atm_european_call))


def test_put_price_helper_matches_dispatcher(atm_european_put: OptionContract) -> None:
    via_helper = put_price(
        atm_european_put.spot,
        atm_european_put.strike,
        atm_european_put.time_to_expiry,
        atm_european_put.rate,
        atm_european_put.dividend_yield,
        atm_european_put.volatility,
    )
    assert via_helper == pytest.approx(black_scholes_price(atm_european_put))


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        ("spot", 0.0),
        ("spot", -1.0),
        ("strike", 0.0),
        ("strike", -10.0),
        ("time_to_expiry", -0.1),
        ("volatility", -0.01),
    ],
)
def test_invalid_inputs_raise(
    atm_european_call: OptionContract, field: str, bad_value: float
) -> None:
    bad = replace(atm_european_call, **{field: bad_value})
    with pytest.raises(ValueError):
        black_scholes_price(bad)


# --- Greeks ----------------------------------------------------------------


def test_delta_call_minus_delta_put_equals_dividend_discount(
    atm_european_call: OptionContract,
    atm_european_put: OptionContract,
) -> None:
    # For continuous q: delta_c - delta_p = exp(-qT).
    expected = math.exp(
        -atm_european_call.dividend_yield * atm_european_call.time_to_expiry
    )
    assert delta(atm_european_call) - delta(atm_european_put) == pytest.approx(expected)


def test_call_delta_in_unit_interval(atm_european_call: OptionContract) -> None:
    d = delta(atm_european_call)
    assert 0.0 < d < 1.0


def test_put_delta_in_negative_unit_interval(atm_european_put: OptionContract) -> None:
    d = delta(atm_european_put)
    assert -1.0 < d < 0.0


def test_gamma_and_vega_are_symmetric_across_call_and_put(
    atm_european_call: OptionContract,
    atm_european_put: OptionContract,
) -> None:
    assert gamma(atm_european_call) == pytest.approx(gamma(atm_european_put))
    assert vega(atm_european_call) == pytest.approx(vega(atm_european_put))


def test_gamma_and_vega_are_positive(atm_european_call: OptionContract) -> None:
    assert gamma(atm_european_call) > 0
    assert vega(atm_european_call) > 0


def test_call_rho_positive_put_rho_negative(
    atm_european_call: OptionContract,
    atm_european_put: OptionContract,
) -> None:
    assert rho(atm_european_call) > 0
    assert rho(atm_european_put) < 0


def test_theta_typically_negative_for_long_atm(atm_european_call: OptionContract) -> None:
    assert theta(atm_european_call) < 0


def test_delta_matches_finite_difference(atm_european_call: OptionContract) -> None:
    bump = 1e-4 * atm_european_call.spot
    up = black_scholes_price(replace(atm_european_call, spot=atm_european_call.spot + bump))
    dn = black_scholes_price(replace(atm_european_call, spot=atm_european_call.spot - bump))
    fd = (up - dn) / (2 * bump)
    assert delta(atm_european_call) == pytest.approx(fd, rel=1e-5, abs=1e-7)


def test_gamma_matches_finite_difference(atm_european_call: OptionContract) -> None:
    bump = 1e-3 * atm_european_call.spot
    base = black_scholes_price(atm_european_call)
    up = black_scholes_price(replace(atm_european_call, spot=atm_european_call.spot + bump))
    dn = black_scholes_price(replace(atm_european_call, spot=atm_european_call.spot - bump))
    fd = (up - 2 * base + dn) / (bump * bump)
    assert gamma(atm_european_call) == pytest.approx(fd, rel=1e-3, abs=1e-6)


def test_vega_matches_finite_difference(atm_european_call: OptionContract) -> None:
    bump = 1e-5
    up = black_scholes_price(
        replace(atm_european_call, volatility=atm_european_call.volatility + bump)
    )
    dn = black_scholes_price(
        replace(atm_european_call, volatility=atm_european_call.volatility - bump)
    )
    fd = (up - dn) / (2 * bump)
    assert vega(atm_european_call) == pytest.approx(fd, rel=1e-5, abs=1e-7)


def test_rho_matches_finite_difference(atm_european_call: OptionContract) -> None:
    bump = 1e-6
    up = black_scholes_price(replace(atm_european_call, rate=atm_european_call.rate + bump))
    dn = black_scholes_price(replace(atm_european_call, rate=atm_european_call.rate - bump))
    fd = (up - dn) / (2 * bump)
    assert rho(atm_european_call) == pytest.approx(fd, rel=1e-4, abs=1e-6)


def test_theta_matches_finite_difference(atm_european_call: OptionContract) -> None:
    # theta == d(V)/d(calendar time) == -d(V)/d(time_to_expiry).
    bump = 1e-6
    up = black_scholes_price(
        replace(atm_european_call, time_to_expiry=atm_european_call.time_to_expiry + bump)
    )
    dn = black_scholes_price(
        replace(atm_european_call, time_to_expiry=atm_european_call.time_to_expiry - bump)
    )
    fd = -(up - dn) / (2 * bump)
    assert theta(atm_european_call) == pytest.approx(fd, rel=1e-4, abs=1e-4)


def test_greeks_collapse_at_expiry(atm_european_call: OptionContract) -> None:
    expiring = replace(atm_european_call, time_to_expiry=0.0)
    assert gamma(expiring) == 0.0
    assert vega(expiring) == 0.0
    assert theta(expiring) == 0.0
    assert rho(expiring) == 0.0


def test_zero_volatility_greeks(atm_european_call: OptionContract) -> None:
    zero_vol = replace(atm_european_call, volatility=0.0)
    assert gamma(zero_vol) == 0.0
    assert vega(zero_vol) == 0.0


def test_american_contract_is_priced_as_european() -> None:
    # The pricer is documented to ignore exercise_style — make that explicit.
    european = OptionContract(
        spot=100.0,
        strike=100.0,
        time_to_expiry=0.5,
        rate=0.045,
        dividend_yield=0.0,
        volatility=0.20,
        option_type=OptionType.CALL,
        exercise_style=ExerciseStyle.EUROPEAN,
    )
    american = replace(european, exercise_style=ExerciseStyle.AMERICAN)
    assert black_scholes_price(european) == pytest.approx(black_scholes_price(american))
