"""Volatility surface construction and interpolation."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from options_platform.pricing.base import OptionContract, OptionType
from options_platform.volatility.implied_vol import implied_volatility


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
        if time_to_expiry < 0 or strike <= 0 or self.grid.empty:
            raise ValueError("surface is empty or point is invalid")
        times = np.asarray(self.grid.index, dtype=float)
        strikes = np.asarray(self.grid.columns, dtype=float)
        if np.isnan(self.grid.to_numpy(dtype=float)).all():
            raise ValueError("surface has no valid implied volatilities")
        # Interpolate along strike for each expiry, then along expiry.  NaN rows
        # are ignored, and endpoints are flat-extrapolated for stable UI plots.
        log_k = np.log(strikes)
        values: list[float] = []
        valid_times: list[float] = []
        for t, row in zip(times, self.grid.to_numpy(dtype=float), strict=True):
            valid = np.isfinite(row)
            if valid.any():
                values.append(float(np.interp(np.log(strike), log_k[valid], row[valid])))
                valid_times.append(float(t))
        return float(np.interp(time_to_expiry, valid_times, values))

    def as_arrays(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Return (T, K, sigma) meshgrid arrays for plotting."""
        times = np.asarray(self.grid.index, dtype=float)
        strikes = np.asarray(self.grid.columns, dtype=float)
        k_grid, t_grid = np.meshgrid(strikes, times)
        return t_grid, k_grid, self.grid.to_numpy(dtype=float)


def build_surface(option_chain: pd.DataFrame) -> VolSurface:
    """Construct a :class:`VolSurface` from a raw option chain frame.

    Expected columns: ``expiry``, ``strike``, ``option_type``, ``market_price``,
    plus the usual market context (spot, rate, dividend).
    """
    required = {"expiry", "strike", "option_type", "market_price", "spot"}
    if not required.issubset(option_chain.columns):
        raise ValueError(f"option_chain must contain {sorted(required)}")
    frame = option_chain.copy()
    expiry = pd.to_datetime(frame["expiry"], utc=True)
    now = pd.Timestamp.now(tz="UTC")
    frame["time_to_expiry"] = frame.get("time_to_expiry", (expiry - now).dt.total_seconds() / (365.25 * 86400)).astype(float)
    def solve(row: pd.Series) -> float:
        option_type = OptionType(str(row.option_type).lower())
        contract = OptionContract(float(row.spot), float(row.strike), float(row.time_to_expiry), float(row.get("rate", 0.05)), float(row.get("dividend_yield", 0.0)), 0.2, option_type)
        value = implied_volatility(float(row.market_price), contract)
        return np.nan if value is None else value
    frame["implied_vol"] = frame.apply(solve, axis=1)
    frame = frame[np.isfinite(frame.implied_vol) & (frame.time_to_expiry > 0)]
    grid = frame.pivot_table(index="time_to_expiry", columns="strike", values="implied_vol", aggfunc="median").sort_index().sort_index(axis=1)
    return VolSurface(grid)
