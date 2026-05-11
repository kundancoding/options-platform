"""Tests for the P&L attribution module."""

from __future__ import annotations

import pytest

from options_platform.analytics import attribute_pnl


@pytest.mark.skip(reason="attribution not yet implemented")
def test_components_sum_to_total() -> None:
    _ = attribute_pnl
    raise NotImplementedError
