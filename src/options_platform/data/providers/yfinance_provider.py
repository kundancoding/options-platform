"""yfinance-backed market-data provider."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from options_platform.data.providers.base import MarketDataProvider


class YFinanceProvider(MarketDataProvider):
    """Fetch quotes, chains and OHLCV data through yfinance."""

    def history(self, symbol: str, start: datetime, end: datetime) -> pd.DataFrame:
        import yfinance as yf
        frame = yf.Ticker(symbol).history(start=start, end=end, auto_adjust=False)
        frame.columns = [str(column).lower().replace(" ", "_") for column in frame.columns]
        return frame.loc[:, ["open", "high", "low", "close", "volume"]]

    def option_chain(self, underlying: str, expiry: datetime | None = None) -> pd.DataFrame:
        import yfinance as yf
        ticker = yf.Ticker(underlying)
        date = expiry.strftime("%Y-%m-%d") if expiry else (ticker.options[0] if ticker.options else None)
        if date is None:
            return pd.DataFrame()
        chain = ticker.option_chain(date)
        legs: list[pd.DataFrame] = []
        for option_type, source in (("call", chain.calls), ("put", chain.puts)):
            frame = source.copy()
            frame["option_type"] = option_type
            frame["expiry"] = date
            frame["underlying"] = underlying.upper()
            frame["market_price"] = frame["lastPrice"].where(frame["lastPrice"] > 0, (frame["bid"] + frame["ask"]) / 2)
            legs.append(frame)
        return pd.concat(legs, ignore_index=True)

    def quote(self, symbol: str) -> dict[str, float]:
        import yfinance as yf
        info = yf.Ticker(symbol).fast_info
        last = float(info.get("last_price") or 0.0)
        return {"bid": float(info.get("bid") or last), "ask": float(info.get("ask") or last), "last": last, "volume": float(info.get("last_volume") or 0.0)}
