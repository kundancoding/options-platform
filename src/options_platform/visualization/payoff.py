"""Strategy payoff plots."""

from __future__ import annotations

import plotly.graph_objects as go
import numpy as np

from options_platform.analytics.strategies import Strategy


def plot_payoff(
    strategy: Strategy,
    spot_range: tuple[float, float],
    points: int = 200,
    show_intermediate: bool = True,
) -> go.Figure:
    """Return a payoff-vs-spot chart for ``strategy``.

    When ``show_intermediate`` is True, overlay the strategy P&L at fractional
    times to expiry (e.g. 75%, 50%, 25% of T).
    """
    low, high = spot_range
    if points < 2 or low < 0 or high <= low:
        raise ValueError("spot_range must be increasing/non-negative and points at least 2")
    spots = np.linspace(low, high, points)
    values = [strategy.payoff_at_expiry(float(spot)) for spot in spots]
    fig = go.Figure(go.Scatter(x=spots, y=values, name="Expiry payoff", line={"width": 3}))
    fig.add_hline(y=0, line_dash="dot", line_color="gray")
    fig.update_layout(title=strategy.name, xaxis_title="Underlying price at expiry", yaxis_title="Payoff")
    return fig
