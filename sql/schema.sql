-- options_platform: canonical SQLite schema.
-- Keep this in sync with options_platform/data/models.py.

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- Instruments: underlyings and option contracts.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS instruments (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol              TEXT NOT NULL UNIQUE,
    asset_class         TEXT NOT NULL CHECK (asset_class IN ('equity', 'option')),
    underlying_symbol   TEXT,
    option_type         TEXT CHECK (option_type IN ('call', 'put')),
    strike              REAL,
    expiry              TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_instruments_underlying
    ON instruments (underlying_symbol);

-- ---------------------------------------------------------------------------
-- Quotes: time-series of bid/ask/last for any instrument.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS quotes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    instrument_id   INTEGER NOT NULL REFERENCES instruments(id) ON DELETE CASCADE,
    ts              TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    bid             REAL NOT NULL,
    ask             REAL NOT NULL,
    last            REAL NOT NULL,
    volume          INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_quotes_instrument_ts
    ON quotes (instrument_id, ts DESC);

-- ---------------------------------------------------------------------------
-- Orders: paper-trading submissions.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS orders (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id            TEXT NOT NULL UNIQUE,
    instrument_id       INTEGER NOT NULL REFERENCES instruments(id),
    side                TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
    quantity            INTEGER NOT NULL,
    order_type          TEXT NOT NULL CHECK (order_type IN ('market', 'limit', 'stop', 'stop_limit')),
    limit_price         REAL,
    stop_price          REAL,
    status              TEXT NOT NULL CHECK (status IN ('pending', 'partial', 'filled', 'cancelled', 'rejected')),
    filled_quantity     INTEGER NOT NULL DEFAULT 0,
    avg_fill_price      REAL NOT NULL DEFAULT 0.0,
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_orders_status ON orders (status);

-- ---------------------------------------------------------------------------
-- Fills: executed slices of orders.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fills (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id    TEXT NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    ts          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    quantity    INTEGER NOT NULL,
    price       REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fills_order ON fills (order_id);

-- ---------------------------------------------------------------------------
-- Positions: current holdings, one row per instrument.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS positions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    instrument_id   INTEGER NOT NULL UNIQUE REFERENCES instruments(id) ON DELETE CASCADE,
    quantity        INTEGER NOT NULL DEFAULT 0,
    avg_cost        REAL NOT NULL DEFAULT 0.0,
    realized_pnl    REAL NOT NULL DEFAULT 0.0,
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------------------------
-- Portfolio snapshots: equity curve and P&L over time.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts              TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    cash            REAL NOT NULL,
    equity          REAL NOT NULL,
    realized_pnl    REAL NOT NULL DEFAULT 0.0,
    unrealized_pnl  REAL NOT NULL DEFAULT 0.0
);

CREATE INDEX IF NOT EXISTS idx_snapshots_ts ON portfolio_snapshots (ts DESC);

-- ---------------------------------------------------------------------------
-- Schema metadata (consumed by scripts/init_db.py).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER PRIMARY KEY,
    applied_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
