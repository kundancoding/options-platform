"""Interactive option-pricing dashboard."""

from __future__ import annotations

import streamlit as st

from options_platform.pricing import ExerciseStyle, OptionContract, OptionType, binomial_price, black_scholes_price, compute_greeks, monte_carlo_price
from options_platform.visualization.greeks_charts import plot_greeks_vs_spot


def render() -> None:
    st.header("Option Pricing")
    st.caption("Black–Scholes, binomial trees, Monte Carlo, and analytic Greeks.")
    left, right = st.columns(2)
    with left:
        spot = st.number_input("Spot", min_value=0.01, value=100.0)
        strike = st.number_input("Strike", min_value=0.01, value=100.0)
        days = st.number_input("Days to expiry", min_value=0, value=90)
        volatility = st.number_input("Volatility (%)", min_value=0.0, value=20.0) / 100
    with right:
        rate = st.number_input("Risk-free rate (%)", value=4.5) / 100
        dividend = st.number_input("Dividend yield (%)", value=0.0) / 100
        option_type = OptionType(st.selectbox("Type", ["call", "put"]))
        american = st.checkbox("American exercise", value=False)
    contract = OptionContract(spot, strike, days / 365.25, rate, dividend, volatility, option_type, ExerciseStyle.AMERICAN if american else ExerciseStyle.EUROPEAN)
    bs, tree, mc = black_scholes_price(contract), binomial_price(contract, steps=300), monte_carlo_price(contract, paths=30_000, seed=7)
    columns = st.columns(3)
    columns[0].metric("Black–Scholes", f"${bs:,.4f}")
    columns[1].metric("Binomial (300 steps)", f"${tree:,.4f}")
    columns[2].metric("Monte Carlo", f"${mc:,.4f}")
    greek = compute_greeks(contract)
    st.dataframe({"Greek": ["Delta", "Gamma", "Vega", "Theta/year", "Rho"], "Value": [greek.delta, greek.gamma, greek.vega, greek.theta, greek.rho]}, hide_index=True, use_container_width=True)
    st.plotly_chart(plot_greeks_vs_spot(contract, (spot * 0.5, spot * 1.5)), use_container_width=True)


render()
