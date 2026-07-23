"""Live view of the in-session paper-trading portfolio."""

from __future__ import annotations

import streamlit as st


def render() -> None:
    st.header("Portfolio")
    st.caption("Paper-account positions and realized P&L from this browser session.")
    if "broker" not in st.session_state:
        st.info("Submit a paper order from the Trading page to create a portfolio.")
        return
    account = st.session_state.broker.portfolio
    positions = list(account.positions.values())
    marks = {position.symbol: st.number_input(f"Mark: {position.symbol}", min_value=0.0, value=float(position.avg_cost), key=f"mark-{position.symbol}") for position in positions}
    equity = account.equity(marks)
    realized = sum(position.realized_pnl for position in positions)
    first, second, third = st.columns(3)
    first.metric("Cash", f"${account.cash:,.2f}")
    second.metric("Equity", f"${equity:,.2f}")
    third.metric("Realized P&L", f"${realized:,.2f}")
    st.dataframe({"Symbol": [p.symbol for p in positions], "Quantity": [p.quantity for p in positions], "Average cost": [p.avg_cost for p in positions], "Mark": [marks[p.symbol] for p in positions], "Unrealized P&L": [p.unrealized_pnl(marks[p.symbol]) for p in positions], "Realized P&L": [p.realized_pnl for p in positions]}, hide_index=True, use_container_width=True)


render()
