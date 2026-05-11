"""Volatility surface construction and interpolation."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class VolSurface:
    """A discretized implied-vol surface over (expiry, strike).

    ``grid`` is indexed by expiry (rows) and strike (columns) with implied
    volatilities as values. ``interpolate`` returns the vol at an arbitrary
    (T, K) point.
    """

    grid: pd.DataFrame

    def interpolate(self, time_to_expiry: float, strike: float) -> float:
        """Return the implied vol at the given (T, K)."""
        # TODO: bilinear interpolation in (T, log-moneyness) space.
        raise NotImplementedError

    def as_arrays(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Return (T, K, sigma) meshgrid arrays for plotting."""
        # TODO: derive from self.grid.
        raise NotImplementedError


def build_surface(option_chain: pd.DataFrame) -> VolSurface:
    """Construct a :class:`VolSurface` from a raw option chain frame.

    Expected columns: ``expiry``, ``strike``, ``option_type``, ``market_price``,
    plus the usual market context (spot, rate, dividend).
    """
    # TODO: per-row IV solve, then pivot into a (T x K) grid; optionally smooth.
    raise NotImplementedError
