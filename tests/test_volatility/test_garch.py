"""Tests for the GARCH(1,1) volatility module."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from options_platform.volatility.garch import (
    DEFAULT_FORECAST_HORIZON,
    GarchFit,
    fit_garch,
    garch_forecast,
    garch_volatility,
)


def _gbm_prices(
    n: int = 1500, sigma_per_period: float = 0.012, seed: int = 0
) -> pd.Series:
    rng = np.random.default_rng(seed)
    increments = rng.normal(0.0, sigma_per_period, size=n)
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    return pd.Series(100 * np.exp(np.cumsum(increments)), index=idx, name="price")


def _garch_simulated_prices(
    n: int = 1500,
    omega: float = 0.05,
    alpha: float = 0.08,
    beta: float = 0.90,
    seed: int = 1,
) -> pd.Series:
    """Simulate a GARCH(1,1) return path (in percentage units) and integrate."""
    rng = np.random.default_rng(seed)
    eps = np.zeros(n)
    sigma2 = np.zeros(n)
    sigma2[0] = omega / (1.0 - alpha - beta)
    for t in range(1, n):
        sigma2[t] = omega + alpha * eps[t - 1] ** 2 + beta * sigma2[t - 1]
        eps[t] = np.sqrt(sigma2[t]) * rng.standard_normal()
    # eps is in "percent" units; convert to fractional returns.
    fractional_returns = eps / 100.0
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    return pd.Series(100 * np.exp(np.cumsum(fractional_returns)), index=idx)


# --- Basic fit --------------------------------------------------------------


def test_fit_garch_returns_garchfit_dataclass() -> None:
    prices = _gbm_prices(n=500, seed=1)
    fit = fit_garch(prices)
    assert isinstance(fit, GarchFit)
    assert isinstance(fit.conditional_volatility, pd.Series)
    assert fit.conditional_volatility.name == "garch_vol"


def test_fit_garch_converges_on_normal_sample() -> None:
    prices = _gbm_prices(n=800, seed=2)
    fit = fit_garch(prices)
    assert fit.converged is True


def test_fit_garch_params_contain_garch_terms() -> None:
    prices = _gbm_prices(n=500, seed=3)
    fit = fit_garch(prices)
    assert "omega" in fit.params
    assert "alpha[1]" in fit.params
    assert "beta[1]" in fit.params


def test_fit_garch_recovers_garch_simulated_parameters() -> None:
    """When the DGP is GARCH(1,1), recover alpha/beta within rough tolerance."""
    prices = _garch_simulated_prices(n=4000, omega=0.05, alpha=0.08, beta=0.90, seed=4)
    fit = fit_garch(prices)
    assert fit.converged is True
    alpha = fit.params["alpha[1]"]
    beta = fit.params["beta[1]"]
    # Loose tolerance — finite-sample MLE has nontrivial variance.
    assert alpha == pytest.approx(0.08, abs=0.05)
    assert beta == pytest.approx(0.90, abs=0.07)
    # Stationarity should hold.
    assert alpha + beta < 1.0


# --- Annualization ----------------------------------------------------------


def test_fit_garch_volatility_is_annualized() -> None:
    """Daily fits with sigma ~= 1.2% should yield ~19% annualized."""
    prices = _gbm_prices(n=1500, sigma_per_period=0.012, seed=5)
    fit = fit_garch(prices)
    last = fit.conditional_volatility.iloc[-1]
    expected = 0.012 * np.sqrt(252)
    assert last == pytest.approx(expected, rel=0.40)


def test_fit_garch_custom_periods_per_year_scales() -> None:
    prices = _gbm_prices(n=600, seed=6)
    fit_252 = fit_garch(prices, periods_per_year=252)
    fit_365 = fit_garch(prices, periods_per_year=365)
    ratio = (
        fit_365.conditional_volatility.iloc[-1]
        / fit_252.conditional_volatility.iloc[-1]
    )
    assert ratio == pytest.approx(np.sqrt(365 / 252), rel=1e-3)


def test_fit_garch_volatility_aligned_to_returns() -> None:
    """Output series should be indexed by the same trading days as the returns."""
    prices = _gbm_prices(n=500, seed=7)
    fit = fit_garch(prices)
    # Returns drop one row vs prices (the first), so vol has len = len(prices) - 1.
    assert len(fit.conditional_volatility) == len(prices) - 1
    assert fit.conditional_volatility.notna().all()


# --- Forecasting ------------------------------------------------------------


def test_garch_forecast_shape() -> None:
    prices = _gbm_prices(n=500, seed=8)
    fit = fit_garch(prices)
    fc = garch_forecast(fit, horizon=10)
    assert isinstance(fc, pd.DataFrame)
    expected_cols = [f"h={h}" for h in range(1, 11)] + ["cumulative_vol"]
    assert list(fc.columns) == expected_cols
    assert len(fc) == 1  # single forecast origin


def test_garch_forecast_mean_reverts_when_persistent() -> None:
    """If alpha + beta < 1, forecasts must drift toward the unconditional vol."""
    prices = _garch_simulated_prices(
        n=3000, omega=0.08, alpha=0.10, beta=0.85, seed=9
    )
    fit = fit_garch(prices)
    if fit.unconditional_volatility is None:
        pytest.skip("Fit was non-stationary; mean reversion test not applicable.")
    fc = garch_forecast(fit, horizon=60)
    row = fc.iloc[-1]
    near = row["h=60"]
    far = row["h=1"]
    uncond = fit.unconditional_volatility
    # Vol forecasts should be monotonic in horizon when starting away from uncond.
    if abs(far - uncond) > 1e-6:
        # Distance to uncond should not increase with horizon.
        assert abs(near - uncond) <= abs(far - uncond) + 1e-9


def test_garch_forecast_default_horizon() -> None:
    prices = _gbm_prices(n=400, seed=10)
    fit = fit_garch(prices)
    fc = garch_forecast(fit)
    assert fc.shape[1] == DEFAULT_FORECAST_HORIZON + 1  # +1 for cumulative


def test_garch_forecast_rejects_invalid_horizon() -> None:
    prices = _gbm_prices(n=400, seed=11)
    fit = fit_garch(prices)
    with pytest.raises(ValueError):
        garch_forecast(fit, horizon=0)
    with pytest.raises(TypeError):
        garch_forecast(fit, horizon=1.5)  # type: ignore[arg-type]


def test_garch_forecast_rejects_non_fit_input() -> None:
    with pytest.raises(TypeError):
        garch_forecast("not a fit", horizon=5)  # type: ignore[arg-type]


def test_garch_forecast_values_are_positive_and_finite() -> None:
    prices = _gbm_prices(n=600, seed=12)
    fit = fit_garch(prices)
    fc = garch_forecast(fit, horizon=10)
    assert (fc.to_numpy() >= 0).all()
    assert np.isfinite(fc.to_numpy()).all()


# --- Input validation -------------------------------------------------------


def test_fit_garch_rejects_invalid_pq() -> None:
    prices = _gbm_prices(n=200, seed=13)
    with pytest.raises(ValueError):
        fit_garch(prices, p=0, q=0)
    with pytest.raises(ValueError):
        fit_garch(prices, p=-1)


def test_fit_garch_rejects_bad_periods() -> None:
    prices = _gbm_prices(n=200, seed=14)
    with pytest.raises(ValueError):
        fit_garch(prices, periods_per_year=0)


def test_fit_garch_rejects_bad_return_scale() -> None:
    prices = _gbm_prices(n=200, seed=15)
    with pytest.raises(ValueError):
        fit_garch(prices, return_scale=0)
    with pytest.raises(ValueError):
        fit_garch(prices, return_scale=-1.0)


def test_fit_garch_returns_input_passthrough() -> None:
    """If the caller passes returns directly, we should not log-diff again."""
    prices = _gbm_prices(n=400, seed=16)
    returns = np.log(prices / prices.shift(1)).dropna()
    fit_a = fit_garch(prices)
    fit_b = fit_garch(returns, is_returns=True)
    # The two should produce nearly identical fits; tolerate tiny numerical drift.
    assert fit_a.params["alpha[1]"] == pytest.approx(fit_b.params["alpha[1]"], abs=1e-6)
    assert fit_a.params["beta[1]"] == pytest.approx(fit_b.params["beta[1]"], abs=1e-6)


# --- Convenience wrapper ----------------------------------------------------


def test_garch_volatility_wrapper() -> None:
    prices = _gbm_prices(n=400, seed=17)
    vol = garch_volatility(prices)
    assert isinstance(vol, pd.Series)
    assert vol.name == "garch_vol"
    assert vol.notna().all()
    assert (vol > 0).all()


# --- Convergence handling ---------------------------------------------------


def test_fit_garch_converged_flag_is_bool() -> None:
    prices = _gbm_prices(n=200, seed=18)
    fit = fit_garch(prices)
    assert isinstance(fit.converged, bool)


def test_fit_garch_small_sample_does_not_crash() -> None:
    """Very small samples emit a warning but still return a fit."""
    prices = _gbm_prices(n=30, seed=19)
    fit = fit_garch(prices, max_iter=50)
    assert isinstance(fit, GarchFit)
    # Should still produce a vol series even if asymptotics are dubious.
    assert len(fit.conditional_volatility) > 0
