"""Lightweight input validators used across the library."""

from __future__ import annotations


def validate_positive(value: float, name: str = "value") -> float:
    """Return ``value`` if strictly positive; otherwise raise ``ValueError``."""
    if value <= 0:
        raise ValueError(f"{name} must be > 0, got {value!r}")
    return value


def validate_probability(p: float, name: str = "p") -> float:
    """Return ``p`` if in (0, 1); otherwise raise ``ValueError``."""
    if not 0.0 < p < 1.0:
        raise ValueError(f"{name} must be in (0, 1), got {p!r}")
    return p
