-- Optional dev/demo seed data for the local SQLite database.

INSERT OR IGNORE INTO instruments (symbol, asset_class, underlying_symbol)
VALUES
    ('SPY', 'equity', NULL),
    ('AAPL', 'equity', NULL),
    ('NVDA', 'equity', NULL);

INSERT OR IGNORE INTO portfolio_snapshots (cash, equity)
VALUES (100000.0, 100000.0);
