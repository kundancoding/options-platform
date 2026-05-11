"""Greeks-vs-spot / Greeks-vs-time charts."""

from __future__ import annotations

import plotly.graph_objects as go

from options_platform.pricing.base import OptionContract


def plot_greeks_vs_spot(
    contract: OptionContract,
    spot_range: tuple[float, float],
    points: int = 200,
) -> go.Figure:
    """Return a multi-trace figure of delta / gamma / vega / theta vs. spot."""
    # TODO: sweep spot; call compute_greeks for each; one trace per Greek.
    raise NotImplementedError
