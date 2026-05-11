# Options Platform

A modular quantitative options pricing and paper-trading platform built in Python.

## Features

- **Pricing models**: Black-Scholes, Binomial trees, Monte Carlo, analytic Greeks.
- **Volatility tooling**: implied vol solvers, historical estimators, surface & smile fitting.
- **Analytics**: P&L attribution, scenario analysis, strategy payoff modelling.
- **Paper trading**: order book, position manager, portfolio bookkeeping, fill simulation.
- **Persistence**: SQLite-backed repository pattern with versioned schema.
- **Visualization**: Plotly charts for payoffs, Greeks, vol surfaces, P&L.
- **Frontend**: multi-page Streamlit app for interactive exploration.

## Project layout

```
options-platform/
├── app/                       # Streamlit UI
├── src/options_platform/      # Library code (pricing, vol, analytics, trading, data, viz)
├── sql/                       # Schema & migrations
├── tests/                     # Pytest suite mirroring src/ layout
├── scripts/                   # Operational helpers (db init, seeding)
├── notebooks/                 # Exploratory analysis
└── .streamlit/                # Streamlit runtime config
```

## Quick start

```bash
# 1. Create a virtual env (Python 3.11+)
python -m venv .venv && source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt
pip install -e .

# 3. Initialize the local SQLite database
python scripts/init_db.py

# 4. Launch the Streamlit app
streamlit run app/main.py
```

## Docker

```bash
docker build -t options-platform .
docker run -p 8501:8501 options-platform
```

## Testing

```bash
pytest -q
```

## Status

Scaffold only — module logic is intentionally left as placeholders.
