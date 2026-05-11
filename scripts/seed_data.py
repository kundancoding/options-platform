"""Optional: seed demo market data into the local SQLite database.

Pulls a few months of OHLCV history for a handful of tickers via yfinance and
inserts it through the repository layer. Intended for development only.
"""

from __future__ import annotations

import argparse


DEFAULT_TICKERS = ("SPY", "AAPL", "NVDA", "QQQ")


def seed(tickers: tuple[str, ...] = DEFAULT_TICKERS, lookback_days: int = 180) -> None:
    """Fetch and persist demo history for ``tickers``."""
    # TODO:
    # 1) instantiate YFinanceProvider + MarketDataService
    # 2) for each ticker, pull history(start=now - lookback_days, end=now)
    # 3) upsert into quotes via QuoteRepository.
    _ = (tickers, lookback_days)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo market data.")
    parser.add_argument("--tickers", nargs="*", default=list(DEFAULT_TICKERS))
    parser.add_argument("--lookback-days", type=int, default=180)
    args = parser.parse_args()

    seed(tuple(args.tickers), args.lookback_days)
    print(f"Seeded {len(args.tickers)} tickers (last {args.lookback_days}d).")


if __name__ == "__main__":
    main()
