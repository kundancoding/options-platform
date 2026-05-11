"""Pricing page — value a single option contract under several models."""

from __future__ import annotations

import streamlit as st

from app.config import get_settings
from options_platform.pricing import black_scholes, binomial, monte_carlo, greeks
from options_platform.visualization import greeks_charts


def render() -> None:
    settings = get_settings()
    st.header("Option Pricing")
    st.caption("Black-Scholes, binomial trees, and Monte Carlo with full Greeks.")

    # TODO: input widgets (S, K, T, r, q, sigma, option type, model selector).
    # TODO: call into options_platform.pricing.* and display side-by-side prices.
    # TODO: render Greeks vs. spot / time via greeks_charts.
    st.info("Pricing UI scaffold — implementation pending.")

    _ = (settings, black_scholes, binomial, monte_carlo, greeks, greeks_charts)


render()
