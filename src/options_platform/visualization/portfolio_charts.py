"""Portfolio-level charts — equity curve, exposure, aggregate Greeks."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go


def plot_equity_curve(snapshots: pd.DataFrame) -> go.Figure:
    """Plot total equity over time from a snapshots DataFrame.

    ``snapshots`` is expected to have columns ``ts`` and ``equity``.
    """
    if not {"ts", "equity"}.issubset(snapshots.columns):
        raise ValueError("snapshots must contain ts and equity columns")
    fig = go.Figure(go.Scatter(x=snapshots["ts"], y=snapshots["equity"], mode="lines", name="Equity"))
    fig.update_layout(title="Portfolio equity", xaxis_title="Time", yaxis_title="Equity")
    return fig
