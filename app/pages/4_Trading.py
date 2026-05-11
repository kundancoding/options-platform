"""Trading page — submit paper orders to the simulated broker."""

from __future__ import annotations

import streamlit as st

from options_platform.trading import execution, order, paper_broker, position


def render() -> None:
    st.header("Paper Trading")
    st.caption("Submit simulated orders and inspect resulting positions.")

    # TODO: order entry form (symbol, side, qty, type, limit/stop, TIF).
    # TODO: call paper_broker.submit(...) and display the resulting fill / rejection.
    # TODO: open orders + recent fills tables.
    st.info("Trading UI scaffold — implementation pending.")

    _ = (execution, order, paper_broker, position)


render()
