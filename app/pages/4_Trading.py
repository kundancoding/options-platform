"""Paper-trading order entry and position state."""

from __future__ import annotations

import streamlit as st

from options_platform.trading import Order, OrderSide, OrderType, PaperBroker, Portfolio


def render() -> None:
    st.header("Paper Trading")
    st.caption("All orders are simulated; no live trades are sent.")
    if "broker" not in st.session_state:
        st.session_state.broker = PaperBroker(Portfolio())
    broker = st.session_state.broker
    with st.form("order"):
        symbol = st.text_input("Symbol", "SPY").upper()
        side = OrderSide(st.selectbox("Side", ["buy", "sell"]))
        quantity = st.number_input("Quantity", min_value=1, value=1)
        order_type = OrderType(st.selectbox("Order type", ["market", "limit"]))
        limit = st.number_input("Limit price", min_value=0.0, value=100.0)
        bid, ask = st.number_input("Bid", min_value=0.0, value=99.95), st.number_input("Ask", min_value=0.0, value=100.05)
        submit = st.form_submit_button("Submit paper order")
    if submit:
        submitted = Order(symbol, side, int(quantity), order_type, limit_price=limit if order_type is OrderType.LIMIT else None)
        result = broker.submit(submitted, {"bid": bid, "ask": ask})
        st.success(f"{result.status.value}: {result.filled_quantity} @ {result.avg_fill_price:.4f}" if result.filled_quantity else result.status.value)
    st.metric("Cash", f"${broker.portfolio.cash:,.2f}")
    positions = list(broker.portfolio.positions.values())
    st.dataframe({"Symbol": [p.symbol for p in positions], "Quantity": [p.quantity for p in positions], "Average cost": [p.avg_cost for p in positions], "Realized P&L": [p.realized_pnl for p in positions]}, hide_index=True, use_container_width=True)


render()
