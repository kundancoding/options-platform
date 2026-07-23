"""Scenario analysis — sweep portfolio P&L over (spot, vol, time) grids."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class ScenarioGrid:
    """Result of a 2-D portfolio P&L sweep."""

    spot_axis: np.ndarray
    vol_axis: np.ndarray
    pnl: np.ndarray  # shape (len(vol_axis), len(spot_axis))

    def to_frame(self) -> pd.DataFrame:
        """Return the grid as a DataFrame indexed by vol, columns spot."""
        return pd.DataFrame(self.pnl, index=self.vol_axis, columns=self.spot_axis).rename_axis("volatility", axis=0).rename_axis("spot", axis=1)


def run_scenarios(
    portfolio: object,
    *,
    spot_range: tuple[float, float, int],
    vol_range: tuple[float, float, int],
    horizon_days: int = 0,
) -> ScenarioGrid:
    """Compute portfolio P&L on a (spot, vol) mesh ``horizon_days`` ahead."""
    spots = np.linspace(*spot_range)
    vols = np.linspace(*vol_range)
    if not hasattr(portfolio, "scenario_value"):
        raise TypeError("portfolio must implement scenario_value(spot=, volatility=, horizon_days=)")
    base = float(portfolio.scenario_value(spot=float(spots[len(spots)//2]), volatility=float(vols[len(vols)//2]), horizon_days=0))
    pnl = np.array([[float(portfolio.scenario_value(spot=float(s), volatility=float(v), horizon_days=horizon_days)) - base for s in spots] for v in vols])
    return ScenarioGrid(spots, vols, pnl)
