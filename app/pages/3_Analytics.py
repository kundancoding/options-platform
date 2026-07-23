"""Interactive option-strategy payoff analysis."""

from __future__ import annotations

import streamlit as st

from options_platform.analytics.strategies import build_strategy
from options_platform.visualization.payoff import plot_payoff


def render() -> None:
    st.header("Analytics")
    st.caption("Strategy construction and expiry payoff analysis.")
    kind = st.selectbox("Strategy", ["long_call", "long_put", "bull_call_spread", "bear_put_spread", "straddle", "strangle", "iron_condor", "butterfly"])
    left, right = st.columns(2)
    with left:
        spot = st.number_input("Current spot", min_value=1.0, value=100.0)
        strike = st.number_input("Centre strike", min_value=1.0, value=100.0)
    with right:
        width = st.number_input("Wing / spread width", min_value=0.1, value=10.0)
        days = st.number_input("Days to expiry", min_value=1, value=90)
    strategy = build_strategy(kind, spot=spot, strike=strike, width=width, time_to_expiry=days / 365.25)
    st.plotly_chart(plot_payoff(strategy, (max(0.0, spot * 0.4), spot * 1.6)), use_container_width=True)
    st.dataframe({"Type": [leg.contract.option_type.value for leg in strategy.legs], "Strike": [leg.contract.strike for leg in strategy.legs], "Quantity": [leg.quantity for leg in strategy.legs]}, hide_index=True, use_container_width=True)


render()
