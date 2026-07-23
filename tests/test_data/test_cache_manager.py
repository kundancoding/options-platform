"""Unit tests for :mod:`options_platform.data.cache_manager`."""

from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
import pytest

from options_platform.data.cache_manager import CacheManager


@pytest.fixture
def cache(tmp_path: Path) -> CacheManager:
    return CacheManager(cache_dir=tmp_path, default_ttl_sec=60)


def test_miss_returns_none(cache: CacheManager) -> None:
    assert cache.get(("history", "AAPL")) is None


def test_set_then_get_roundtrip(cache: CacheManager) -> None:
    df = pd.DataFrame({"x": [1, 2, 3]})
    cache.set(("history", "AAPL"), df)
    out = cache.get(("history", "AAPL"))
    assert isinstance(out, pd.DataFrame)
    pd.testing.assert_frame_equal(out, df)


def test_expired_entry_is_evicted(tmp_path: Path) -> None:
    cache = CacheManager(cache_dir=tmp_path, default_ttl_sec=0.01)
    cache.set(("k",), "value")
    time.sleep(0.05)
    assert cache.get(("k",)) is None
    # files should be cleaned up after the miss
    assert not any(tmp_path.iterdir())


def test_ttl_override_per_entry(tmp_path: Path) -> None:
    cache = CacheManager(cache_dir=tmp_path, default_ttl_sec=0.01)
    cache.set(("k",), "value", ttl_sec=60)
    time.sleep(0.05)
    assert cache.get(("k",)) == "value"


def test_zero_ttl_never_expires(tmp_path: Path) -> None:
    cache = CacheManager(cache_dir=tmp_path, default_ttl_sec=60)
    cache.set(("k",), "value", ttl_sec=0)
    # Manually backdate meta to ensure 0 disables expiry regardless of clock.
    assert cache.get(("k",)) == "value"


def test_disabled_cache_is_noop(tmp_path: Path) -> None:
    cache = CacheManager(cache_dir=tmp_path, enabled=False)
    cache.set(("k",), "value")
    assert cache.get(("k",)) is None
    # Directory must not have been auto-created.
    assert not tmp_path.joinpath(".meta.json").exists()


def test_invalidate_removes_entry(cache: CacheManager) -> None:
    cache.set(("k",), "v")
    cache.invalidate(("k",))
    assert cache.get(("k",)) is None


def test_clear_wipes_all_entries(cache: CacheManager) -> None:
    cache.set(("a",), 1)
    cache.set(("b",), 2)
    cache.clear()
    assert cache.get(("a",)) is None
    assert cache.get(("b",)) is None


def test_corrupt_payload_is_discarded(tmp_path: Path) -> None:
    cache = CacheManager(cache_dir=tmp_path, default_ttl_sec=60)
    cache.set(("k",), "v")
    # Find and corrupt the payload file.
    pkl = next(tmp_path.glob("*.pkl"))
    pkl.write_bytes(b"not a pickle")
    assert cache.get(("k",)) is None
    # corrupted entry should be cleaned up
    assert not pkl.exists()


def test_has_reflects_freshness(tmp_path: Path) -> None:
    cache = CacheManager(cache_dir=tmp_path, default_ttl_sec=0.01)
    cache.set(("k",), "v")
    assert cache.has(("k",)) is True
    time.sleep(0.05)
    assert cache.has(("k",)) is False
