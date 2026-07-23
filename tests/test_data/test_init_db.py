"""Tests for the ``scripts/init_db.py`` bootstrap entry point."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from sqlalchemy import inspect

from options_platform.data.database import Database
from options_platform.data.models import Base

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "init_db.py"


@pytest.fixture(scope="module")
def init_db_module():
    """Import ``scripts/init_db.py`` as a module (it is not on sys.path)."""
    spec = importlib.util.spec_from_file_location("init_db", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["init_db"] = module
    spec.loader.exec_module(module)
    return module


def test_create_schema_is_idempotent(tmp_path) -> None:
    """Running create_schema twice should not raise."""
    url = f"sqlite:///{tmp_path / 'idem.db'}"
    db = Database.create(url=url)
    try:
        Base.metadata.create_all(db.engine)
        Base.metadata.create_all(db.engine)  # second call is a no-op
        live = set(inspect(db.engine).get_table_names())
        assert set(Base.metadata.tables.keys()).issubset(live)
    finally:
        db.dispose()


def test_main_creates_and_validates(tmp_path, init_db_module) -> None:
    db_path = tmp_path / "boot.db"
    exit_code = init_db_module.main(["--db", str(db_path)])
    assert exit_code == 0
    assert db_path.exists()

    db = Database.create(url=f"sqlite:///{db_path}")
    try:
        live = set(inspect(db.engine).get_table_names())
        assert set(Base.metadata.tables.keys()).issubset(live)
    finally:
        db.dispose()


def test_main_validate_only_detects_missing_tables(
    tmp_path, init_db_module, capsys
) -> None:
    db_path = tmp_path / "empty.db"
    # Create an empty SQLite file with no tables.
    db = Database.create(url=f"sqlite:///{db_path}")
    db.dispose()

    exit_code = init_db_module.main(["--db", str(db_path), "--validate-only"])
    assert exit_code == 1
    err = capsys.readouterr().err
    assert "missing tables" in err


def test_main_drop_recreates_clean_schema(tmp_path, init_db_module) -> None:
    db_path = tmp_path / "drop.db"
    assert init_db_module.main(["--db", str(db_path)]) == 0

    # Insert a row so we can confirm --drop wipes data.
    db = Database.create(url=f"sqlite:///{db_path}")
    try:
        from options_platform.data.models import AssetClass, Instrument

        with db.session_scope() as s:
            s.add(Instrument(symbol="WIPE", asset_class=AssetClass.EQUITY))
    finally:
        db.dispose()

    assert init_db_module.main(["--db", str(db_path), "--drop"]) == 0

    db = Database.create(url=f"sqlite:///{db_path}")
    try:
        from options_platform.data.repository import InstrumentRepository

        with db.session_scope() as s:
            assert InstrumentRepository(s).get_by_symbol("WIPE") is None
    finally:
        db.dispose()


def test_coerce_url_handles_bare_path(tmp_path, init_db_module) -> None:
    url = init_db_module._coerce_url(str(tmp_path / "x.db"))
    assert url.startswith("sqlite:///")
    assert url.endswith("x.db")


def test_coerce_url_passes_url_through(init_db_module) -> None:
    url = init_db_module._coerce_url("sqlite:///:memory:")
    assert url == "sqlite:///:memory:"
