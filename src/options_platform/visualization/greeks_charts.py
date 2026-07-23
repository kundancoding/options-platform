"""Greeks-vs-spot / Greeks-vs-time charts."""

from __future__ import annotations

import plotly.graph_objects as go
import numpy as np
from dataclasses import replace

from options_platform.pricing.base import OptionContract
from options_platform.pricing.greeks import compute_greeks


def plot_greeks_vs_spot(
    contract: OptionContract,
    spot_range: tuple[float, float],
    points: int = 200,
) -> go.Figure:
    """Return a multi-trace figure of delta / gamma / vega / theta vs. spot."""
    low, high = spot_range
    if low <= 0 or high <= low or points < 2:
        raise ValueError("spot_range must be positive/increasing and points at least 2")
    spots = np.linspace(low, high, points)
    data = [compute_greeks(replace(contract, spot=float(spot))) for spot in spots]
    fig = go.Figure()
    for name in ("delta", "gamma", "vega", "theta", "rho"):
        fig.add_trace(go.Scatter(x=spots, y=[getattr(greek, name) for greek in data], name=name.title()))
    fig.update_layout(title="Greeks vs. spot", xaxis_title="Spot", yaxis_title="Sensitivity")
    return fig
