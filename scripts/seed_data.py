"""Fetch reproducible demo OHLCV CSV files for local exploration."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

from options_platform.data.market_data import MarketDataService
from options_platform.data.providers.yfinance_provider import YFinanceProvider

DEFAULT_TICKERS = ("SPY", "AAPL", "NVDA", "QQQ")
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "data"


def seed(tickers: tuple[str, ...] = DEFAULT_TICKERS, lookback_days: int = 180) -> None:
    """Fetch and save OHLCV history for each ticker as a local CSV file."""
    if lookback_days < 1:
        raise ValueError("lookback_days must be positive")
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=lookback_days)
    service = MarketDataService(YFinanceProvider())
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for ticker in tickers:
        symbol = ticker.strip().upper()
        if not symbol:
            continue
        history = service.history(symbol, start, end)
        history.to_csv(OUTPUT_DIR / f"{symbol}_history.csv", index=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo market-data CSV files.")
    parser.add_argument("--tickers", nargs="*", default=list(DEFAULT_TICKERS))
    parser.add_argument("--lookback-days", type=int, default=180)
    args = parser.parse_args()
    seed(tuple(args.tickers), args.lookback_days)
    print(f"Seeded {len(args.tickers)} tickers (last {args.lookback_days}d).")


if __name__ == "__main__":
    main()
