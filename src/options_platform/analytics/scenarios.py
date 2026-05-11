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
        # TODO: pd.DataFrame(self.pnl, index=self.vol_axis, columns=self.spot_axis).
        raise NotImplementedError


def run_scenarios(
    portfolio: object,
    *,
    spot_range: tuple[float, float, int],
    vol_range: tuple[float, float, int],
    horizon_days: int = 0,
) -> ScenarioGrid:
    """Compute portfolio P&L on a (spot, vol) mesh ``horizon_days`` ahead."""
    # TODO: build linspaces; reprice portfolio at each grid point.
    raise NotImplementedError
