"""Volatility-smile fitting (per-expiry slice)."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class SmileFit:
    """Parametric fit of a single-expiry vol smile."""

    expiry: pd.Timestamp
    params: dict[str, float]

    def sigma(self, strike: float) -> float:
        """Return the fitted implied vol at ``strike``."""
        # TODO: evaluate the chosen parameterization (SVI / SABR / polynomial).
        raise NotImplementedError


def fit_smile(slice_: pd.DataFrame, model: str = "svi") -> SmileFit:
    """Fit a smile model to a single-expiry strike-vs-IV slice.

    Parameters
    ----------
    slice_:
        DataFrame with columns ``strike`` and ``implied_vol``.
    model:
        One of ``"svi"``, ``"sabr"``, ``"poly3"``.
    """
    # TODO: dispatch on model; solve with scipy.optimize.least_squares.
    raise NotImplementedError
