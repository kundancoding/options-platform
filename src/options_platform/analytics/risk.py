"""Portfolio risk metrics: VaR, expected shortfall, deterministic stress."""

from __future__ import annotations

import math

import numpy as np


def portfolio_var(portfolio: object, *, confidence: float = 0.99, horizon_days: int = 1, method: str = "historical") -> float:
    """Return a positive loss estimate from a portfolio returns series.

    ``portfolio`` supplies ``returns`` (periodic fractional returns) and either
    ``current_value`` or ``cash``.  This small protocol keeps risk analysis
    independent of storage and broker implementations.
    """
    if not 0 < confidence < 1 or horizon_days < 1:
        raise ValueError("confidence must be in (0, 1) and horizon_days must be positive")
    returns = np.asarray(getattr(portfolio, "returns", []), dtype=float)
    if returns.size < 2 or not np.isfinite(returns).all():
        raise ValueError("portfolio must expose at least two finite returns")
    value = float(getattr(portfolio, "current_value", getattr(portfolio, "cash", 0.0)))
    if value < 0:
        raise ValueError("portfolio value must be non-negative")
    scale = math.sqrt(horizon_days)
    if method == "historical":
        quantile = float(np.quantile(returns, 1 - confidence))
    elif method == "parametric":
        from scipy.stats import norm
        quantile = float(returns.mean() - norm.ppf(confidence) * returns.std(ddof=1)) * scale
    elif method == "monte_carlo":
        rng = np.random.default_rng(0)
        samples = rng.normal(returns.mean() * horizon_days, returns.std(ddof=1) * scale, 20_000)
        quantile = float(np.quantile(samples, 1 - confidence))
    else:
        raise ValueError("method must be historical, parametric, or monte_carlo")
    return max(0.0, -quantile * value * (scale if method == "historical" else 1.0))


def stress_test(portfolio: object, shocks: dict[str, float]) -> float:
    """Return the P&L from deterministic shocks using ``scenario_value``.

    The required scenario-value protocol makes the function usable for an
    options portfolio without baking a market model into the risk module.
    """
    value = getattr(portfolio, "scenario_value", None)
    if not callable(value):
        raise TypeError("portfolio must implement scenario_value(spot=, volatility=, horizon_days=)")
    base_spot = float(shocks.get("base_spot", 1.0))
    base_vol = float(shocks.get("base_volatility", 0.0))
    spot = base_spot * (1.0 + float(shocks.get("spot", 0.0)))
    vol = max(0.0, base_vol + float(shocks.get("volatility", shocks.get("vol", 0.0))))
    days = int(shocks.get("horizon_days", 0))
    return float(value(spot=spot, volatility=vol, horizon_days=days) - value(spot=base_spot, volatility=base_vol, horizon_days=0))
