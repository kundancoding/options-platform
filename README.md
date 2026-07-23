# Options Platform

A modular Python platform for option valuation, volatility analysis, strategy
payoffs, and simulated paper trading. It is intended for research and learning;
it does not place live trades or provide investment advice.

## What is included

- **Pricing:** Black-Scholes-Merton, Cox-Ross-Rubinstein binomial trees
  (including American exercise), Monte Carlo pricing, and analytic Greeks.
- **Volatility:** implied-volatility solving, historical realized-volatility
  estimators, EWMA/GARCH forecasting, regime labels, smiles, and surfaces.
- **Analytics:** common option strategies, expiry payoff diagrams, Greek P&L
  attribution, two-dimensional scenarios, VaR, and deterministic stress tests.
- **Paper trading:** market, limit, stop, and stop-limit fill simulation;
  position accounting, cash, realized/unrealized P&L, and aggregate Greeks.
- **Data:** cached yfinance market data, normalized provider interfaces, and
  SQLite repositories for instruments, positions, trades, forecasts, and
  portfolio snapshots.
- **Dashboard:** Streamlit pages for pricing, realized volatility, strategy
  analysis, paper-order entry, and portfolio marks.

## Project layout

```text
options-platform/
├── app/                       # Streamlit dashboard and pages
├── src/options_platform/      # Pricing, volatility, analytics, trading, data, charts
├── sql/                       # SQLite schema and migrations
├── tests/                     # Pytest suite
├── scripts/                   # Database setup and demo-data helpers
├── data/                      # Local generated data (not committed)
└── .streamlit/                # Streamlit configuration
```

## Quick start

Python 3.11 or newer is required.

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
python scripts/init_db.py
streamlit run app/main.py
```

### macOS / Linux

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
python scripts/init_db.py
streamlit run app/main.py
```

Open the local URL printed by Streamlit (normally `http://localhost:8501`).

## Market data

The Volatility page can fetch daily bars through yfinance. To save demo OHLCV
CSV files locally, run:

```bash
python scripts/seed_data.py --tickers SPY AAPL NVDA QQQ --lookback-days 180
```

Market-data availability is controlled by Yahoo Finance and may be delayed,
incomplete, or unavailable. The dashboard's pricing and paper-trading pages
also work with manually entered values.

## Testing

```bash
pytest -q
```

## Docker

```bash
docker build -t options-platform .
docker run --rm -p 8501:8501 options-platform
```

## Disclaimer

This project is an educational paper-trading and analytics tool. Verify all
calculations independently before using them for a financial decision.
