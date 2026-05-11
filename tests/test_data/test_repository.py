"""Tests for the repository layer (in-memory SQLite)."""

from __future__ import annotations

import pytest

from options_platform.data import OrderRepository, PositionRepository, QuoteRepository


@pytest.mark.skip(reason="repository methods not yet implemented")
def test_quote_repository_round_trip() -> None:
    _ = (OrderRepository, PositionRepository, QuoteRepository)
    raise NotImplementedError
