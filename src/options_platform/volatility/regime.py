"""Volatility-regime detection via rolling percentile thresholds.

Classifies each observation in a volatility series into one of a small set
of regimes (e.g. ``low`` / ``normal`` / ``high``) based on its position in
the *rolling* empirical distribution of past volatility. The rolling design
is important: a regime label that depends on the *full-sample* distribution
leaks future information and produces an unrealistically clean signal.

Two thresholding strategies are supported:

* **Quantile** (default): low/high cutoffs are the rolling percentiles of
  the vol series itself. Adapts to the realized vol regime of the asset.
* **Absolute**: low/high cutoffs are fixed constants supplied by the
  caller. Useful when comparing across assets or against a target.

Two label schemes are supported: two-state ``("low", "high")`` and
three-state ``("low", "normal", "high")``. Output dtype is pandas
``CategoricalDtype`` with the regime ordering preserved, so callers can
group/aggregate safely.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

import numpy as np
import pandas as pd

from options_platform.utils.logging import get_logger

logger = get_logger(__name__)

DEFAULT_LOW_PERCENTILE: Final[float] = 0.33
DEFAULT_HIGH_PERCENTILE: Final[float] = 0.67
DEFAULT_WINDOW: Final[int] = 252

TWO_STATE_LABELS: Final[tuple[str, str]] = ("low", "high")
THREE_STATE_LABELS: Final[tuple[str, str, str]] = ("low", "normal", "high")

RegimeMode = Literal["two_state", "three_state"]


@dataclass(frozen=True)
class RegimeResult:
    """Output of :func:`label_regimes` and friends.

    Attributes
    ----------
    labels:
        Categorical series of regime labels aligned to the input index.
    low_threshold:
        Per-observation low cutoff (rolling) or scalar (absolute mode).
    high_threshold:
        Per-observation high cutoff (rolling) or scalar (absolute mode).
    mode:
        ``"two_state"`` or ``"three_state"``.
    """

    labels: pd.Series
    low_threshold: pd.Series | float
    high_threshold: pd.Series | float
    mode: RegimeMode


def _validate_percentiles(low: float, high: float) -> None:
    for name, value in (("low_percentile", low), ("high_percentile", high)):
        if not np.isfinite(value):
            raise ValueError(f"{name} must be finite, got {value}")
        if not 0.0 < value < 1.0:
            raise ValueError(f"{name} must lie in (0, 1), got {value}")
    if low >= high:
        raise ValueError(
            f"low_percentile must be strictly less than high_percentile, "
            f"got low={low}, high={high}"
        )


def _validate_window(window: int, *, min_value: int = 2) -> None:
    if not isinstance(window, int) or isinstance(window, bool):
        raise TypeError(f"window must be int, got {type(window).__name__}")
    if window < min_value:
        raise ValueError(f"window must be >= {min_value}, got {window}")


def _validate_series(vol: pd.Series) -> pd.Series:
    if not isinstance(vol, pd.Series):
        raise TypeError(f"vol must be a pandas Series, got {type(vol).__name__}")
    if vol.empty:
        raise ValueError("vol is empty")
    return vol.astype("float64")


def _categorical(values: pd.Series, *, mode: RegimeMode) -> pd.Series:
    """Coerce a string-typed series into an ordered categorical."""
    categories = THREE_STATE_LABELS if mode == "three_state" else TWO_STATE_LABELS
    dtype = pd.CategoricalDtype(categories=list(categories), ordered=True)
    return values.astype(dtype)


def rolling_thresholds(
    vol: pd.Series,
    *,
    window: int = DEFAULT_WINDOW,
    low_percentile: float = DEFAULT_LOW_PERCENTILE,
    high_percentile: float = DEFAULT_HIGH_PERCENTILE,
    min_periods: int | None = None,
) -> pd.DataFrame:
    """Compute rolling percentile thresholds of a vol series.

    Parameters
    ----------
    vol:
        Annualized volatility series (any source — historical, EWMA, GARCH).
    window:
        Rolling lookback length.
    low_percentile, high_percentile:
        Quantiles in ``(0, 1)`` with ``low < high``.
    min_periods:
        Minimum observations in the window for a threshold to be emitted.
        Defaults to ``window``.

    Returns
    -------
    pd.DataFrame
        Columns ``low`` and ``high`` indexed like ``vol``.
    """
    _validate_window(window)
    _validate_percentiles(low_percentile, high_percentile)
    series = _validate_series(vol)
    effective_min = window if min_periods is None else min_periods

    rolling = series.rolling(window=window, min_periods=effective_min)
    low = rolling.quantile(low_percentile)
    high = rolling.quantile(high_percentile)
    out = pd.DataFrame({"low": low, "high": high})
    out.index.name = vol.index.name
    return out


def label_regimes(
    vol: pd.Series,
    *,
    window: int = DEFAULT_WINDOW,
    low_percentile: float = DEFAULT_LOW_PERCENTILE,
    high_percentile: float = DEFAULT_HIGH_PERCENTILE,
    mode: RegimeMode = "three_state",
    min_periods: int | None = None,
) -> RegimeResult:
    """Rolling percentile-based regime labels.

    For each observation ``v_t``, compares against the rolling percentiles
    of the prior ``window`` observations and emits:

    * ``"low"`` if ``v_t <= low_threshold_t``
    * ``"high"`` if ``v_t >= high_threshold_t``
    * ``"normal"`` (three-state) or ``"low"`` / ``"high"`` (two-state)
      otherwise.

    In two-state mode the median (50th percentile) is used as the single
    cutoff regardless of ``low_percentile`` / ``high_percentile``.

    Parameters
    ----------
    vol:
        Annualized vol series.
    window:
        Rolling lookback length.
    low_percentile, high_percentile:
        Quantile cutoffs for three-state mode. Ignored in two-state mode.
    mode:
        ``"two_state"`` for low/high, ``"three_state"`` for low/normal/high.
    min_periods:
        Minimum observations in the window. Defaults to ``window``;
        observations before this threshold receive NaN labels.

    Returns
    -------
    RegimeResult
        Categorical labels plus the rolling thresholds.
    """
    series = _validate_series(vol)
    if mode not in ("two_state", "three_state"):
        raise ValueError(f"mode must be 'two_state' or 'three_state', got {mode!r}")

    if mode == "two_state":
        # Median cutoff; the explicit percentile args are unused but we
        # still validate them to keep the API uniform.
        _validate_window(window)
        effective_min = window if min_periods is None else min_periods
        cutoff = series.rolling(window=window, min_periods=effective_min).quantile(0.5)
        labels = pd.Series(np.nan, index=series.index, dtype="object")
        valid = cutoff.notna() & series.notna()
        labels[valid & (series <= cutoff)] = "low"
        labels[valid & (series > cutoff)] = "high"
        result_labels = _categorical(labels, mode=mode)
        result_labels.name = "regime"
        logger.debug(
            "regime.label_two_state",
            window=window,
            n_labeled=int(valid.sum()),
        )
        return RegimeResult(
            labels=result_labels,
            low_threshold=cutoff,
            high_threshold=cutoff,
            mode=mode,
        )

    thresholds = rolling_thresholds(
        series,
        window=window,
        low_percentile=low_percentile,
        high_percentile=high_percentile,
        min_periods=min_periods,
    )
    low = thresholds["low"]
    high = thresholds["high"]
    labels = pd.Series(np.nan, index=series.index, dtype="object")
    valid = low.notna() & high.notna() & series.notna()
    labels[valid & (series <= low)] = "low"
    labels[valid & (series >= high)] = "high"
    labels[valid & (series > low) & (series < high)] = "normal"

    result_labels = _categorical(labels, mode=mode)
    result_labels.name = "regime"
    logger.debug(
        "regime.label_three_state",
        window=window,
        low_percentile=low_percentile,
        high_percentile=high_percentile,
        n_labeled=int(valid.sum()),
    )
    return RegimeResult(
        labels=result_labels,
        low_threshold=low,
        high_threshold=high,
        mode=mode,
    )


def absolute_threshold_regimes(
    vol: pd.Series,
    *,
    low_threshold: float,
    high_threshold: float,
) -> RegimeResult:
    """Classify each observation against fixed absolute thresholds.

    Useful when comparing volatility across assets or against a target
    operating regime that is not vol-specific (e.g. "vol > 30% is high
    risk regardless of asset").

    Parameters
    ----------
    vol:
        Annualized vol series.
    low_threshold, high_threshold:
        Scalar cutoffs in the same units as ``vol``. Must satisfy
        ``low_threshold < high_threshold``.

    Returns
    -------
    RegimeResult
        Three-state labels using the absolute cutoffs.
    """
    if not (np.isfinite(low_threshold) and np.isfinite(high_threshold)):
        raise ValueError(
            f"thresholds must be finite, got low={low_threshold}, high={high_threshold}"
        )
    if low_threshold >= high_threshold:
        raise ValueError(
            f"low_threshold must be strictly less than high_threshold, "
            f"got low={low_threshold}, high={high_threshold}"
        )
    series = _validate_series(vol)

    labels = pd.Series(np.nan, index=series.index, dtype="object")
    valid = series.notna()
    labels[valid & (series <= low_threshold)] = "low"
    labels[valid & (series >= high_threshold)] = "high"
    labels[valid & (series > low_threshold) & (series < high_threshold)] = "normal"
    result_labels = _categorical(labels, mode="three_state")
    result_labels.name = "regime"

    logger.debug(
        "regime.absolute_threshold",
        low_threshold=low_threshold,
        high_threshold=high_threshold,
        n_labeled=int(valid.sum()),
    )
    return RegimeResult(
        labels=result_labels,
        low_threshold=low_threshold,
        high_threshold=high_threshold,
        mode="three_state",
    )


def regime_summary(result: RegimeResult) -> pd.Series:
    """Frequency table (proportions) of regime labels.

    NaN labels are excluded from the denominator.
    """
    if not isinstance(result, RegimeResult):
        raise TypeError(
            f"result must be a RegimeResult, got {type(result).__name__}"
        )
    counts = result.labels.value_counts(dropna=True, normalize=True)
    counts.name = "proportion"
    return counts


__all__ = [
    "DEFAULT_HIGH_PERCENTILE",
    "DEFAULT_LOW_PERCENTILE",
    "DEFAULT_WINDOW",
    "RegimeResult",
    "THREE_STATE_LABELS",
    "TWO_STATE_LABELS",
    "absolute_threshold_regimes",
    "label_regimes",
    "regime_summary",
    "rolling_thresholds",
]
