"""Volatility page — implied / historical vol, surfaces and smiles."""

from __future__ import annotations

import streamlit as st

from options_platform.volatility import historical_vol, implied_vol, smile, vol_surface
from options_platform.visualization import vol_charts


def render() -> None:
    st.header("Volatility")
    st.caption("Implied vol solver, historical estimators, surface & smile fitting.")

    # TODO: ticker input → fetch option chain via data layer.
    # TODO: solve IV per strike/expiry; plot smile and full surface.
    # TODO: overlay historical realized vol (close-to-close, Parkinson, Yang-Zhang).
    st.info("Volatility UI scaffold — implementation pending.")

    _ = (historical_vol, implied_vol, smile, vol_surface, vol_charts)


render()
