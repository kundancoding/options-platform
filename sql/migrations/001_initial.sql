-- Migration 001: initial schema.
-- Run by scripts/init_db.py. Subsequent migrations should follow the same
-- numeric prefix convention (002_*.sql, 003_*.sql, ...).

-- The full DDL lives in ../schema.sql; this file just records the version.
-- scripts/init_db.py will execute schema.sql and then INSERT the version row.
INSERT OR IGNORE INTO schema_version (version) VALUES (1);
