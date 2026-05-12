"""On-disk cache for market-data payloads.

Each cached entry is stored as a pickled :class:`pandas.DataFrame` (or
plain Python object) under :attr:`CacheManager.cache_dir`, keyed by a
SHA-256 hash of a descriptor tuple. A sidecar ``.meta.json`` file holds
the entry's creation timestamp and TTL so freshness can be checked
without unpickling the payload.

The cache is intentionally simple: filesystem-only, no eviction loop, no
shared locks. It is suitable for a single-process Streamlit / CLI flow
where the cost of a cache miss is a network round-trip.

Example::

    cache = CacheManager(cache_dir=Path("./.cache"), default_ttl_sec=900)
    df = cache.get(("history", "AAPL", "1y"))
    if df is None:
        df = client.get_history("AAPL", period="1y")
        cache.set(("history", "AAPL", "1y"), df)
"""

from __future__ import annotations

import hashlib
import json
import pickle
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from options_platform.utils.logging import get_logger

logger = get_logger(__name__)


DEFAULT_CACHE_DIR = Path.home() / ".options_platform" / "cache"


@dataclass
class CacheManager:
    """Filesystem-backed key/value cache with per-entry TTL.

    Attributes:
        cache_dir: Directory under which cache files are written. Created
            on first use.
        default_ttl_sec: TTL applied when :meth:`set` is called without an
            explicit ``ttl_sec``. ``0`` disables expiration.
        enabled: When ``False``, every operation becomes a no-op
            (``get`` returns ``None``, ``set`` does not write). Useful for
            tests or `--no-cache` style overrides.
    """

    cache_dir: Path = field(default_factory=lambda: DEFAULT_CACHE_DIR)
    default_ttl_sec: float = 15 * 60
    enabled: bool = True

    def __post_init__(self) -> None:
        self.cache_dir = Path(self.cache_dir)
        if self.enabled:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    # --- public API ---------------------------------------------------

    def get(self, key: Any) -> Any | None:
        """Return the cached value for ``key`` or ``None`` on miss / expiry.

        Args:
            key: Hashable, JSON-serializable descriptor (tuple, str, etc.).

        Returns:
            The previously cached payload, or ``None`` if the key has not
            been written, has expired, or the on-disk file is corrupt.
        """
        if not self.enabled:
            return None

        payload_path, meta_path = self._paths_for(key)
        if not payload_path.exists() or not meta_path.exists():
            return None

        try:
            meta = json.loads(meta_path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Discarding unreadable cache meta {path}: {exc}",
                           path=meta_path, exc=exc)
            self._safe_unlink(payload_path, meta_path)
            return None

        if self._is_expired(meta):
            logger.debug("Cache expired for {key}", key=key)
            self._safe_unlink(payload_path, meta_path)
            return None

        try:
            with payload_path.open("rb") as fp:
                value = pickle.load(fp)  # noqa: S301 - trusted local file
        except (OSError, pickle.UnpicklingError, EOFError) as exc:
            logger.warning("Discarding unreadable cache payload {path}: {exc}",
                           path=payload_path, exc=exc)
            self._safe_unlink(payload_path, meta_path)
            return None

        logger.debug("Cache hit for {key}", key=key)
        return value

    def set(self, key: Any, value: Any, ttl_sec: float | None = None) -> None:
        """Write ``value`` to the cache under ``key``.

        Args:
            key: Hashable, JSON-serializable descriptor.
            value: Any picklable payload (typically a DataFrame).
            ttl_sec: Per-entry override of :attr:`default_ttl_sec`. ``0``
                or a negative value disables expiry for this entry.
        """
        if not self.enabled:
            return

        ttl = self.default_ttl_sec if ttl_sec is None else ttl_sec
        payload_path, meta_path = self._paths_for(key)
        try:
            with payload_path.open("wb") as fp:
                pickle.dump(value, fp, protocol=pickle.HIGHEST_PROTOCOL)
            meta = {
                "key_repr": repr(key),
                "created_at": time.time(),
                "ttl_sec": float(ttl),
            }
            meta_path.write_text(json.dumps(meta))
            logger.debug("Cache wrote {key} (ttl={ttl}s)", key=key, ttl=ttl)
        except (OSError, pickle.PicklingError) as exc:
            logger.warning("Cache write failed for {key}: {exc}", key=key, exc=exc)
            self._safe_unlink(payload_path, meta_path)

    def invalidate(self, key: Any) -> None:
        """Remove the entry for ``key`` if present. No-op on miss."""
        if not self.enabled:
            return
        payload_path, meta_path = self._paths_for(key)
        self._safe_unlink(payload_path, meta_path)

    def clear(self) -> None:
        """Delete every entry in :attr:`cache_dir`."""
        if not self.enabled or not self.cache_dir.exists():
            return
        shutil.rmtree(self.cache_dir, ignore_errors=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def has(self, key: Any) -> bool:
        """Return ``True`` if a fresh (non-expired) entry exists for ``key``."""
        return self.get(key) is not None

    # --- internals ----------------------------------------------------

    def _paths_for(self, key: Any) -> tuple[Path, Path]:
        """Return (payload, meta) paths for ``key``."""
        digest = _hash_key(key)
        return (
            self.cache_dir / f"{digest}.pkl",
            self.cache_dir / f"{digest}.meta.json",
        )

    @staticmethod
    def _is_expired(meta: dict[str, Any]) -> bool:
        ttl = float(meta.get("ttl_sec", 0))
        if ttl <= 0:
            return False
        created = float(meta.get("created_at", 0))
        return (time.time() - created) > ttl

    @staticmethod
    def _safe_unlink(*paths: Path) -> None:
        for path in paths:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass


def _hash_key(key: Any) -> str:
    """Stable SHA-256 hash of a JSON-serializable cache key."""
    try:
        canonical = json.dumps(key, sort_keys=True, default=str)
    except (TypeError, ValueError):
        canonical = repr(key)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
