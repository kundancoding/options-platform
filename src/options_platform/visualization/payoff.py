"""Strategy payoff plots."""

from __future__ import annotations

import plotly.graph_objects as go

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
    # TODO: build numpy linspace; evaluate strategy.payoff_at_expiry; trace.
    raise NotImplementedError
