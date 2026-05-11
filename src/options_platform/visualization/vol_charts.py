"""Smile and surface visualizations."""

from __future__ import annotations

import plotly.graph_objects as go

from options_platform.volatility.smile import SmileFit
from options_platform.volatility.vol_surface import VolSurface


def plot_smile(fit: SmileFit, strikes: list[float]) -> go.Figure:
    """Return a strike-vs-implied-vol line chart for a single expiry."""
    # TODO: scatter of observed IV + fitted curve from fit.sigma(strike).
    raise NotImplementedError


def plot_surface(surface: VolSurface) -> go.Figure:
    """Return a 3-D surface plot of implied vol over (T, K)."""
    # TODO: go.Surface(x=K_grid, y=T_grid, z=sigma_grid).
    raise NotImplementedError
