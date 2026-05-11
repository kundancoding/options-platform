"""Portfolio analytics — strategies, P&L, scenarios, risk."""

from options_platform.analytics.pnl import PnLBreakdown, attribute_pnl
from options_platform.analytics.risk import portfolio_var, stress_test
from options_platform.analytics.scenarios import ScenarioGrid, run_scenarios
from options_platform.analytics.strategies import Strategy, build_strategy

__all__ = [
    "PnLBreakdown",
    "attribute_pnl",
    "portfolio_var",
    "stress_test",
    "ScenarioGrid",
    "run_scenarios",
    "Strategy",
    "build_strategy",
]
