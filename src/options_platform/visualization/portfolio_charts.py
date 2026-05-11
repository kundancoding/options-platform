"""Portfolio-level charts — equity curve, exposure, aggregate Greeks."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go


def plot_equity_curve(snapshots: pd.DataFrame) -> go.Figure:
    """Plot total equity over time from a snapshots DataFrame.

    ``snapshots`` is expected to have columns ``ts`` and ``equity``.
    """
    # TODO: line trace; optional realized/unrealized P&L overlay.
    raise NotImplementedError
