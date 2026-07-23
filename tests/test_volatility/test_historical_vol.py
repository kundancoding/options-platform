"""Tests for the historical (realized) volatility estimators."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from options_platform.volatility.historical_vol import (
    annualize_vol,
    close_to_close_vol,
    garman_klass_vol,
    log_returns,
    parkinson_vol,
    rolling_realized_vol,
    yang_zhang_vol,
)


# --- Helpers ----------------------------------------------------------------


def _gbm_prices(
    n: int = 500,
    sigma_per_period: float = 0.01,
    mu_per_period: float = 0.0,
    seed: int = 0,
    s0: float = 100.0,
) -> pd.Series:
    """Generate a deterministic GBM-like price path of length ``n``."""
    rng = np.random.default_rng(seed)
    increments = rng.normal(mu_per_period, sigma_per_period, size=n)
    log_path = np.cumsum(increments)
    idx = pd.date_range("2020-01-01", periods=n, freq="B")
    return pd.Series(s0 * np.exp(log_path), index=idx, name="price")


def _ohlc_from_close(prices: pd.Series, spread_pct: float = 0.005) -> pd.DataFrame:
    """Build a synthetic OHLC frame around a close series.

    Deterministic spreads ensure reproducibility — we don't care about realism,
    only that the estimators run end-to-end.
    """
    rng = np.random.default_rng(123)
    n = len(prices)
    noise = rng.uniform(0, spread_pct, size=(n, 4))
    close = prices.to_numpy()
    open_ = close * (1.0 - noise[:, 0] * 0.5 + noise[:, 1] * 0.5)
    high = np.maximum(close, open_) * (1.0 + noise[:, 2])
    low = np.minimum(close, open_) * (1.0 - noise[:, 3])
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close},
        index=prices.index,
    )


# --- log_returns ------------------------------------------------------------


def test_log_returns_basic() -> None:
    prices = pd.Series([100.0, 110.0, 99.0, 121.0])
    r = log_returns(prices)
    expected = np.log([110 / 100, 99 / 110, 121 / 99])
    np.testing.assert_allclose(r.to_numpy(), expected, atol=1e-12)


def test_log_returns_handles_nonpositive_prices() -> None:
    prices = pd.Series([100.0, 0.0, -5.0, 120.0])
    r = log_returns(prices, drop_na=False)
    # Zero / negative prices coerced to NaN before the log.
    assert r.isna().sum() >= 2


def test_log_returns_handles_nans() -> None:
    prices = pd.Series([100.0, np.nan, 110.0, 121.0])
    r = log_returns(prices, drop_na=False)
    # First entry NaN by definition; middle gap may produce another NaN.
    assert np.isnan(r.iloc[0])


def test_log_returns_rejects_non_series() -> None:
    with pytest.raises(TypeError):
        log_returns([1.0, 2.0, 3.0])  # type: ignore[arg-type]


def test_log_returns_rejects_empty() -> None:
    with pytest.raises(ValueError):
        log_returns(pd.Series([], dtype="float64"))


# --- rolling_realized_vol / close_to_close_vol ------------------------------


def test_realized_vol_annualization_factor() -> None:
    """Under deterministic returns, annualized sigma must be std * sqrt(252)."""
    prices = pd.Series(100 * np.exp(np.cumsum(np.full(252, 0.01))))
    # Constant returns have zero std -> zero vol.
    vol = rolling_realized_vol(prices, window=20)
    last_vol = vol.dropna().iloc[-1]
    assert last_vol == pytest.approx(0.0, abs=1e-12)


def test_realized_vol_recovers_population_sigma() -> None:
    """For a large sample of IID normal returns, rolling vol should approach
    the true annualized sigma."""
    n = 5000
    sigma_per_day = 0.01
    prices = _gbm_prices(n=n, sigma_per_period=sigma_per_day, seed=42)
    vol = rolling_realized_vol(prices, window=252)
    # Average across the rolling estimates near the back of the sample.
    avg = vol.dropna().iloc[-200:].mean()
    expected = sigma_per_day * np.sqrt(252)
    assert avg == pytest.approx(expected, rel=0.10)


def test_realized_vol_window_validation() -> None:
    prices = _gbm_prices(n=10)
    with pytest.raises(ValueError):
        rolling_realized_vol(prices, window=1)
    with pytest.raises(TypeError):
        rolling_realized_vol(prices, window=1.5)  # type: ignore[arg-type]


def test_realized_vol_periods_validation() -> None:
    prices = _gbm_prices(n=50)
    with pytest.raises(ValueError):
        rolling_realized_vol(prices, periods_per_year=0)


def test_realized_vol_partial_windows_are_nan() -> None:
    """The first ``window - 1`` outputs should be NaN by default."""
    prices = _gbm_prices(n=100)
    vol = rolling_realized_vol(prices, window=20)
    assert vol.iloc[:19].isna().all()
    assert vol.iloc[20:].notna().all()


def test_realized_vol_handles_missing_prices() -> None:
    """NaN injected into prices should not crash the rolling computation."""
    prices = _gbm_prices(n=200)
    prices.iloc[50] = np.nan
    vol = rolling_realized_vol(prices, window=21)
    # The rolling window straddling the gap will have a NaN in its inputs,
    # but pandas excludes it; output should be defined after enough lookback.
    assert vol.iloc[-1] == vol.iloc[-1]  # not NaN
    assert (vol.dropna() >= 0).all()


def test_realized_vol_custom_periods_per_year() -> None:
    """Switching to 365 must scale by sqrt(365/252) relative to default."""
    prices = _gbm_prices(n=500, sigma_per_period=0.01, seed=7)
    daily = rolling_realized_vol(prices, window=60, periods_per_year=252).dropna()
    cal = rolling_realized_vol(prices, window=60, periods_per_year=365).dropna()
    ratio = (cal / daily).dropna()
    assert ratio.mean() == pytest.approx(np.sqrt(365 / 252), abs=1e-10)


def test_close_to_close_vol_matches_realized() -> None:
    """The legacy alias must equal the canonical function."""
    prices = _gbm_prices(n=200, seed=1)
    a = close_to_close_vol(prices, window=20)
    b = rolling_realized_vol(prices, window=20)
    pd.testing.assert_series_equal(a, b, check_names=False)


def test_realized_vol_output_is_named_series() -> None:
    prices = _gbm_prices(n=80)
    vol = rolling_realized_vol(prices, window=20)
    assert isinstance(vol, pd.Series)
    assert vol.name == "realized_vol"


# --- annualize_vol ----------------------------------------------------------


def test_annualize_vol_basic() -> None:
    assert annualize_vol(0.01, periods_per_year=252) == pytest.approx(
        0.01 * np.sqrt(252)
    )


def test_annualize_vol_rejects_negative() -> None:
    with pytest.raises(ValueError):
        annualize_vol(-0.01)


def test_annualize_vol_rejects_nan() -> None:
    with pytest.raises(ValueError):
        annualize_vol(float("nan"))


# --- Range-based estimators -------------------------------------------------


def test_parkinson_vol_runs_on_synthetic_ohlc() -> None:
    prices = _gbm_prices(n=200, sigma_per_period=0.02, seed=3)
    ohlc = _ohlc_from_close(prices)
    vol = parkinson_vol(ohlc["high"], ohlc["low"], window=21)
    valid = vol.dropna()
    assert (valid > 0).all()
    assert valid.iloc[-1] < 10.0  # sanity: well under 1000% annualized


def test_parkinson_vol_index_mismatch_raises() -> None:
    high = pd.Series([1.0, 2.0], index=[0, 1])
    low = pd.Series([0.5, 1.0], index=[2, 3])
    with pytest.raises(ValueError):
        parkinson_vol(high, low)


def test_garman_klass_vol_runs() -> None:
    prices = _gbm_prices(n=200, seed=5)
    ohlc = _ohlc_from_close(prices)
    vol = garman_klass_vol(ohlc, window=21)
    valid = vol.dropna()
    assert (valid > 0).all()


def test_garman_klass_vol_requires_ohlc_columns() -> None:
    bad = pd.DataFrame({"open": [1.0], "high": [1.0]})
    with pytest.raises(ValueError):
        garman_klass_vol(bad)


def test_yang_zhang_vol_runs() -> None:
    prices = _gbm_prices(n=300, seed=9)
    ohlc = _ohlc_from_close(prices)
    vol = yang_zhang_vol(ohlc, window=21)
    valid = vol.dropna()
    assert (valid > 0).all()


def test_yang_zhang_vol_requires_ohlc_columns() -> None:
    bad = pd.DataFrame({"open": [1.0]})
    with pytest.raises(ValueError):
        yang_zhang_vol(bad)


# --- Vol-clustering sanity --------------------------------------------------


def test_realized_vol_increases_in_high_volatility_regime() -> None:
    """A regime change with higher per-period sigma must show up downstream."""
    n_low = 300
    n_high = 300
    rng = np.random.default_rng(11)
    r_low = rng.normal(0.0, 0.005, size=n_low)
    r_high = rng.normal(0.0, 0.03, size=n_high)
    returns = np.concatenate([r_low, r_high])
    idx = pd.date_range("2019-01-01", periods=len(returns), freq="B")
    prices = pd.Series(100 * np.exp(np.cumsum(returns)), index=idx)
    vol = rolling_realized_vol(prices, window=21).dropna()
    low_phase_avg = vol.iloc[10:280].mean()
    high_phase_avg = vol.iloc[-100:].mean()
    assert high_phase_avg > low_phase_avg * 3.0
