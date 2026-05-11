"""Analytics page — strategy payoffs, P&L attribution, scenario analysis."""

from __future__ import annotations

import streamlit as st

from options_platform.analytics import pnl, risk, scenarios, strategies
from options_platform.visualization import payoff


def render() -> None:
    st.header("Analytics")
    st.caption("Strategy builder, payoff diagrams, and scenario / risk analysis.")

    # TODO: strategy selector (covered call, vertical, straddle, iron condor, custom).
    # TODO: payoff curve at expiry + intermediate dates via payoff.plot_payoff.
    # TODO: scenario grid over (spot, vol, time) — heatmap of P&L.
    st.info("Analytics UI scaffold — implementation pending.")

    _ = (pnl, risk, scenarios, strategies, payoff)


render()
