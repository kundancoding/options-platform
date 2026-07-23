"""Volatility dashboard with live history and local realized-vol analytics."""

from __future__ import annotations

import streamlit as st

from options_platform.data.data_fetcher import DataFetcher
from options_platform.volatility.historical_vol import close_to_close_vol, garman_klass_vol, parkinson_vol, yang_zhang_vol


def render() -> None:
    st.header("Volatility")
    st.caption("Fetch daily bars and compare realized-volatility estimators.")
    ticker, period, window = st.columns(3)
    with ticker:
        symbol = st.text_input("Ticker", "SPY").upper()
    with period:
        history_period = st.selectbox("History", ["6mo", "1y", "2y"], index=1)
    with window:
        lookback = st.number_input("Rolling window", min_value=2, max_value=252, value=21)
    if st.button("Fetch volatility data"):
        with st.spinner("Fetching market history..."):
            data = DataFetcher().get_historical_data(symbol, period=history_period)
        if data.empty:
            st.warning("No history returned. Check the ticker or try again later.")
            return
        close = close_to_close_vol(data["close"], window=int(lookback))
        parkinson = parkinson_vol(data["high"], data["low"], window=int(lookback))
        gk = garman_klass_vol(data, window=int(lookback))
        yz = yang_zhang_vol(data, window=int(lookback))
        metrics = {"Close-to-close": close, "Parkinson": parkinson, "Garman–Klass": gk, "Yang–Zhang": yz}
        st.line_chart(metrics)
        latest = {name: series.dropna().iloc[-1] for name, series in metrics.items() if not series.dropna().empty}
        st.dataframe({"Estimator": list(latest), "Annualized volatility": list(latest.values())}, hide_index=True, use_container_width=True)
    else:
        st.info("Choose a ticker and fetch data to calculate realized volatility.")


render()
