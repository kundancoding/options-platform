"""Tests for the EWMA (RiskMetrics) volatility module."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from options_platform.volatility.ewma import (
    DEFAULT_LAMBDA,
    RISKMETRICS_DAILY_LAMBDA,
    RISKMETRICS_MONTHLY_LAMBDA,
    ewma_forecast,
    ewma_variance,
    ewma_volatility,
)


def _gbm_prices(
    n: int = 500, sigma_per_period: float = 0.01, seed: int = 0
) -> pd.Series:
    rng = np.random.default_rng(seed)
    increments = rng.normal(0.0, sigma_per_period, size=n)
    idx = pd.date_range("2020-01-01", periods=n, freq="B")
    return pd.Series(100 * np.exp(np.cumsum(increments)), index=idx, name="price")


# --- Constants --------------------------------------------------------------


def test_default_lambda_matches_riskmetrics() -> None:
    assert DEFAULT_LAMBDA == RISKMETRICS_DAILY_LAMBDA == 0.94
    assert RISKMETRICS_MONTHLY_LAMBDA == 0.97


# --- ewma_variance ----------------------------------------------------------


def test_ewma_variance_recursion_matches_hand_computation() -> None:
    """Spot-check the recursion against a manual unroll."""
    returns = pd.Series([0.01, -0.02, 0.03, 0.0, -0.01])
    lam = 0.9
    out = ewma_variance(returns, lam=lam)
    expected = []
    v_prev: float | None = None
    for r in returns:
        if v_prev is None:
            v_prev = r * r
        else:
            v_prev = lam * v_prev + (1 - lam) * r * r
        expected.append(v_prev)
    np.testing.assert_allclose(out.to_numpy(), expected, atol=1e-15)


def test_ewma_variance_seeded_initial() -> None:
    returns = pd.Series([0.01, -0.02, 0.03])
    lam = 0.94
    seed = 1e-4
    out = ewma_variance(returns, lam=lam, initial_variance=seed)
    # First value: lam * seed + (1 - lam) * r1^2.
    expected_0 = lam * seed + (1 - lam) * (0.01**2)
    assert out.iloc[0] == pytest.approx(expected_0, rel=1e-12)


def test_ewma_variance_rejects_invalid_lambda() -> None:
    returns = pd.Series([0.01, 0.02])
    for bad in (0.0, 1.0, -0.5, 1.5, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            ewma_variance(returns, lam=bad)


def test_ewma_variance_rejects_negative_seed() -> None:
    returns = pd.Series([0.01, 0.02])
    with pytest.raises(ValueError):
        ewma_variance(returns, initial_variance=-1.0)


def test_ewma_variance_handles_internal_nans() -> None:
    """An isolated NaN return should propagate the prior state, not crash."""
    returns = pd.Series([0.01, np.nan, 0.02])
    out = ewma_variance(returns, lam=0.9)
    assert out.notna().all()
    # The NaN step should hold the previous variance.
    assert out.iloc[1] == pytest.approx(out.iloc[0], abs=1e-15)


# --- ewma_volatility --------------------------------------------------------


def test_ewma_volatility_is_annualized_by_default() -> None:
    prices = _gbm_prices(n=500, sigma_per_period=0.01, seed=10)
    vol = ewma_volatility(prices)
    # Should be roughly sigma * sqrt(252) ~= 0.1587.
    valid_tail = vol.dropna().iloc[-200:]
    assert valid_tail.mean() == pytest.approx(0.01 * np.sqrt(252), rel=0.30)


def test_ewma_volatility_annualize_false() -> None:
    prices = _gbm_prices(n=500, sigma_per_period=0.01, seed=11)
    daily = ewma_volatility(prices, annualize=False).dropna().iloc[-200:]
    annual = ewma_volatility(prices, annualize=True).dropna().iloc[-200:]
    ratio = annual / daily
    assert ratio.mean() == pytest.approx(np.sqrt(252), abs=1e-10)


def test_ewma_volatility_lambda_close_to_one_is_smoother() -> None:
    """Higher lambda => longer memory => smaller day-over-day changes."""
    prices = _gbm_prices(n=500, sigma_per_period=0.02, seed=12)
    vol_low = ewma_volatility(prices, lam=0.85).dropna()
    vol_high = ewma_volatility(prices, lam=0.99).dropna()
    var_change_low = vol_low.diff().dropna().var()
    var_change_high = vol_high.diff().dropna().var()
    assert var_change_high < var_change_low


def test_ewma_volatility_rejects_invalid_inputs() -> None:
    with pytest.raises(TypeError):
        ewma_volatility([1, 2, 3])  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        ewma_volatility(pd.Series([], dtype="float64"))
    with pytest.raises(ValueError):
        ewma_volatility(pd.Series([100.0, 101.0]), periods_per_year=-5)


# --- ewma_forecast ----------------------------------------------------------


def test_ewma_forecast_shape() -> None:
    prices = _gbm_prices(n=200, seed=20)
    horizon = 10
    fc = ewma_forecast(prices, horizon=horizon)
    assert isinstance(fc, pd.DataFrame)
    expected_cols = [f"h={h}" for h in range(1, horizon + 1)] + ["cumulative_vol"]
    assert list(fc.columns) == expected_cols
    assert len(fc) == len(prices)


def test_ewma_forecast_is_flat_across_horizon() -> None:
    """Pure EWMA produces a flat conditional-vol forecast — verify."""
    prices = _gbm_prices(n=200, seed=21)
    fc = ewma_forecast(prices, horizon=5).dropna()
    last_row = fc.iloc[-1]
    h1 = last_row["h=1"]
    for h in range(2, 6):
        assert last_row[f"h={h}"] == pytest.approx(h1, abs=1e-12)


def test_ewma_forecast_cumulative_scales_with_sqrt_horizon() -> None:
    """Cumulative vol = sigma * sqrt(H) * sqrt(periods_per_year)."""
    prices = _gbm_prices(n=200, seed=22)
    fc_short = ewma_forecast(prices, horizon=1).dropna().iloc[-1]
    fc_long = ewma_forecast(prices, horizon=4).dropna().iloc[-1]
    # cumulative_long / cumulative_short == sqrt(4) == 2
    assert fc_long["cumulative_vol"] / fc_short["cumulative_vol"] == pytest.approx(
        2.0, rel=1e-10
    )


def test_ewma_forecast_rejects_invalid_horizon() -> None:
    prices = _gbm_prices(n=100, seed=23)
    with pytest.raises(ValueError):
        ewma_forecast(prices, horizon=0)
    with pytest.raises(TypeError):
        ewma_forecast(prices, horizon=1.5)  # type: ignore[arg-type]


# --- Vol clustering sanity --------------------------------------------------


def test_ewma_responds_to_vol_shock() -> None:
    """Inject a regime change; EWMA should pick it up."""
    n_low = 200
    n_high = 200
    rng = np.random.default_rng(31)
    r_low = rng.normal(0.0, 0.005, size=n_low)
    r_high = rng.normal(0.0, 0.04, size=n_high)
    returns = np.concatenate([r_low, r_high])
    idx = pd.date_range("2019-01-01", periods=len(returns), freq="B")
    prices = pd.Series(100 * np.exp(np.cumsum(returns)), index=idx)
    vol = ewma_volatility(prices, lam=0.9)
    pre_shock = vol.iloc[n_low - 20 : n_low].mean()
    post_shock = vol.iloc[-50:].mean()
    assert post_shock > pre_shock * 3.0
