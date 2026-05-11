"""Streamlit entrypoint.

Run with::

    streamlit run app/main.py

Multi-page navigation is wired automatically via the :mod:`app.pages` package —
Streamlit discovers files prefixed with a number and surfaces them in the
sidebar in order.
"""

from __future__ import annotations

import streamlit as st

from app.config import get_settings


def configure_page() -> None:
    """Apply global Streamlit page configuration."""
    settings = get_settings()
    st.set_page_config(
        page_title=settings.app_title,
        page_icon=settings.app_icon,
        layout=settings.layout,
        initial_sidebar_state="expanded",
    )


def render_landing() -> None:
    """Render the landing page (sidebar + welcome card)."""
    settings = get_settings()
    st.title(settings.app_title)
    st.caption("Modular options pricing, analytics and paper trading.")
    st.markdown(
        """
        Use the sidebar to navigate:

        - **Pricing** — value options under Black-Scholes / binomial / Monte Carlo.
        - **Volatility** — implied / historical vol, surfaces and smiles.
        - **Analytics** — strategy payoffs, scenario analysis, risk.
        - **Trading** — submit paper orders and manage positions.
        - **Portfolio** — live P&L, Greeks aggregation, exposure dashboards.
        """
    )


def main() -> None:
    """Top-level entrypoint invoked by ``streamlit run``."""
    configure_page()
    render_landing()


if __name__ == "__main__":
    main()
