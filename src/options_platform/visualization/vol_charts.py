"""Smile and surface visualizations."""

from __future__ import annotations

import plotly.graph_objects as go

from options_platform.volatility.smile import SmileFit
from options_platform.volatility.vol_surface import VolSurface


def plot_smile(fit: SmileFit, strikes: list[float]) -> go.Figure:
    """Return a strike-vs-implied-vol line chart for a single expiry."""
    if not strikes:
        raise ValueError("strikes must not be empty")
    ordered = sorted(float(strike) for strike in strikes)
    fig = go.Figure(go.Scatter(x=ordered, y=[fit.sigma(strike) for strike in ordered], mode="lines", name="Fitted IV"))
    fig.update_layout(title=f"Volatility smile ({fit.expiry.date()})", xaxis_title="Strike", yaxis_title="Implied volatility")
    return fig


def plot_surface(surface: VolSurface) -> go.Figure:
    """Return a 3-D surface plot of implied vol over (T, K)."""
    times, strikes, values = surface.as_arrays()
    fig = go.Figure(go.Surface(x=strikes, y=times, z=values, colorscale="Viridis"))
    fig.update_layout(title="Implied-volatility surface", scene={"xaxis_title": "Strike", "yaxis_title": "Years to expiry", "zaxis_title": "IV"})
    return fig
