"""Portfolio page — aggregated positions, P&L and Greeks dashboards."""

from __future__ import annotations

import streamlit as st

from options_platform.trading import portfolio
from options_platform.visualization import portfolio_charts


def render() -> None:
    st.header("Portfolio")
    st.caption("Live positions, aggregated Greeks, realized & unrealized P&L.")

    # TODO: load portfolio snapshot from the repository layer.
    # TODO: render exposure table + aggregate Greeks bar/line charts.
    # TODO: realized vs unrealized P&L over time.
    st.info("Portfolio UI scaffold — implementation pending.")

    _ = (portfolio, portfolio_charts)


render()
