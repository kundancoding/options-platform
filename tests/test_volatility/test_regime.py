"""Tests for volatility regime detection."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from options_platform.volatility.regime import (
    RegimeResult,
    absolute_threshold_regimes,
    label_regimes,
    regime_summary,
    rolling_thresholds,
)


# --- rolling_thresholds -----------------------------------------------------


def test_rolling_thresholds_returns_low_lt_high() -> None:
    rng = np.random.default_rng(0)
    vol = pd.Series(rng.uniform(0.1, 0.5, size=500))
    th = rolling_thresholds(vol, window=60)
    valid = th.dropna()
    assert (valid["low"] < valid["high"]).all()


def test_rolling_thresholds_partial_windows_are_nan() -> None:
    vol = pd.Series(np.linspace(0.1, 1.0, 100))
    th = rolling_thresholds(vol, window=20)
    assert th["low"].iloc[:19].isna().all()
    assert th["high"].iloc[:19].isna().all()


def test_rolling_thresholds_invalid_percentiles() -> None:
    vol = pd.Series(np.linspace(0.1, 1.0, 100))
    with pytest.raises(ValueError):
        rolling_thresholds(vol, low_percentile=0.7, high_percentile=0.3)
    with pytest.raises(ValueError):
        rolling_thresholds(vol, low_percentile=0.0, high_percentile=0.5)
    with pytest.raises(ValueError):
        rolling_thresholds(vol, low_percentile=0.3, high_percentile=1.0)


def test_rolling_thresholds_quantile_property() -> None:
    """In a window of identical values, low == high == that value."""
    vol = pd.Series(np.full(100, 0.25))
    th = rolling_thresholds(vol, window=20)
    valid = th.dropna()
    assert (valid["low"] == 0.25).all()
    assert (valid["high"] == 0.25).all()


# --- label_regimes (three-state) -------------------------------------------


def test_label_regimes_three_state_categorical_dtype() -> None:
    rng = np.random.default_rng(1)
    vol = pd.Series(rng.uniform(0.1, 0.5, size=400))
    result = label_regimes(vol, window=60)
    assert isinstance(result, RegimeResult)
    assert isinstance(result.labels.dtype, pd.CategoricalDtype)
    assert result.mode == "three_state"
    assert set(result.labels.cat.categories) == {"low", "normal", "high"}


def test_label_regimes_three_state_split_proportions() -> None:
    """With default 0.33/0.67 cutoffs and uniform vol, each state ~1/3."""
    rng = np.random.default_rng(2)
    vol = pd.Series(rng.uniform(0.1, 0.5, size=2000))
    result = label_regimes(vol, window=252)
    valid = result.labels.dropna()
    counts = valid.value_counts(normalize=True)
    # The boundary semantics (<= low, >= high) put boundary observations in
    # both low and high; expect roughly 1/3 each.
    assert counts["low"] == pytest.approx(1 / 3, abs=0.08)
    assert counts["normal"] == pytest.approx(1 / 3, abs=0.08)
    assert counts["high"] == pytest.approx(1 / 3, abs=0.08)


def test_label_regimes_three_state_partial_windows_are_nan() -> None:
    rng = np.random.default_rng(3)
    vol = pd.Series(rng.uniform(0.1, 0.5, size=300))
    result = label_regimes(vol, window=60)
    # First (window - 1) entries should be NaN labels.
    assert result.labels.iloc[:59].isna().all()


def test_label_regimes_high_when_vol_spikes() -> None:
    """A clear spike at the tail must be labelled ``high``."""
    base = np.full(300, 0.15)
    base[-30:] = 0.50  # sharp regime change
    vol = pd.Series(base)
    result = label_regimes(vol, window=60)
    # The spike values should clearly classify as high.
    last_labels = result.labels.dropna().iloc[-10:]
    assert (last_labels == "high").all()


def test_label_regimes_low_when_vol_collapses() -> None:
    """A vol collapse at the tail must be labelled ``low``."""
    base = np.full(300, 0.40)
    base[-30:] = 0.05
    vol = pd.Series(base)
    result = label_regimes(vol, window=60)
    last_labels = result.labels.dropna().iloc[-10:]
    assert (last_labels == "low").all()


# --- label_regimes (two-state) ---------------------------------------------


def test_label_regimes_two_state_uses_median_cutoff() -> None:
    rng = np.random.default_rng(4)
    vol = pd.Series(rng.uniform(0.1, 0.5, size=2000))
    result = label_regimes(vol, window=252, mode="two_state")
    valid = result.labels.dropna()
    counts = valid.value_counts(normalize=True)
    assert set(counts.index) <= {"low", "high"}
    # Median split: each ~50%.
    assert counts["low"] == pytest.approx(0.5, abs=0.06)
    assert counts["high"] == pytest.approx(0.5, abs=0.06)


def test_label_regimes_two_state_threshold_is_scalar_like() -> None:
    """Two-state returns the median series as both low and high thresholds."""
    vol = pd.Series(np.linspace(0.1, 0.5, 300))
    result = label_regimes(vol, window=60, mode="two_state")
    # Same series object semantics: low == high (the median cutoff).
    assert isinstance(result.low_threshold, pd.Series)
    pd.testing.assert_series_equal(result.low_threshold, result.high_threshold)


def test_label_regimes_invalid_mode() -> None:
    vol = pd.Series([0.1, 0.2, 0.3])
    with pytest.raises(ValueError):
        label_regimes(vol, mode="quadrants")  # type: ignore[arg-type]


def test_label_regimes_rejects_empty() -> None:
    with pytest.raises(ValueError):
        label_regimes(pd.Series([], dtype="float64"))


def test_label_regimes_handles_missing_vol() -> None:
    """NaN in the vol series must produce NaN labels, not crash."""
    vol = pd.Series([0.1, np.nan, 0.2, 0.3, 0.4, 0.5, 0.6] * 20)
    result = label_regimes(vol, window=20)
    # The label at the NaN positions must be NaN.
    assert result.labels.iloc[1::7].isna().all()


# --- absolute_threshold_regimes --------------------------------------------


def test_absolute_threshold_regimes_basic() -> None:
    vol = pd.Series([0.05, 0.15, 0.25, 0.35, 0.45])
    result = absolute_threshold_regimes(
        vol, low_threshold=0.10, high_threshold=0.40
    )
    labels = result.labels.tolist()
    assert labels == ["low", "normal", "normal", "normal", "high"]


def test_absolute_threshold_regimes_boundary_inclusive() -> None:
    """Boundary value at low_threshold is ``low`` (<=); at high is ``high`` (>=)."""
    vol = pd.Series([0.10, 0.40])
    result = absolute_threshold_regimes(
        vol, low_threshold=0.10, high_threshold=0.40
    )
    assert result.labels.tolist() == ["low", "high"]


def test_absolute_threshold_regimes_validates_thresholds() -> None:
    vol = pd.Series([0.1, 0.2])
    with pytest.raises(ValueError):
        absolute_threshold_regimes(vol, low_threshold=0.5, high_threshold=0.1)
    with pytest.raises(ValueError):
        absolute_threshold_regimes(
            vol, low_threshold=float("nan"), high_threshold=0.5
        )


def test_absolute_threshold_regimes_no_lookahead() -> None:
    """Absolute mode shouldn't depend on rolling window — labels for each obs
    should be a pure function of that observation."""
    vol = pd.Series([0.05, 0.50, 0.05, 0.50])
    result = absolute_threshold_regimes(
        vol, low_threshold=0.10, high_threshold=0.30
    )
    assert result.labels.tolist() == ["low", "high", "low", "high"]


# --- regime_summary ---------------------------------------------------------


def test_regime_summary_proportions_sum_to_one() -> None:
    rng = np.random.default_rng(5)
    vol = pd.Series(rng.uniform(0.1, 0.5, size=1000))
    result = label_regimes(vol, window=60)
    summary = regime_summary(result)
    assert summary.sum() == pytest.approx(1.0, abs=1e-12)


def test_regime_summary_rejects_non_result() -> None:
    with pytest.raises(TypeError):
        regime_summary("not a result")  # type: ignore[arg-type]
