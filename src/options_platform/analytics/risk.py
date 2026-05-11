"""Portfolio risk metrics — VaR, expected shortfall, deterministic stress."""

from __future__ import annotations


def portfolio_var(
    portfolio: object,
    *,
    confidence: float = 0.99,
    horizon_days: int = 1,
    method: str = "historical",
) -> float:
    """Return the portfolio Value-at-Risk at the given confidence/horizon.

    ``method`` is one of ``"historical"``, ``"parametric"``, ``"monte_carlo"``.
    """
    # TODO: dispatch on method; reuse simulate / reprice utilities.
    raise NotImplementedError


def stress_test(portfolio: object, shocks: dict[str, float]) -> float:
    """Reprice ``portfolio`` under named shocks (e.g. ``{"spot": -0.10}``)."""
    # TODO: apply shocks to a clone of the market context; reprice; return delta.
    raise NotImplementedError
